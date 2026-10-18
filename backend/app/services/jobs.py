"""
Durable background jobs.

Work that should happen after a request (chapter summaries, re-indexing,
voice DNA) is written to the `jobs` table in the same transaction as the
change that needs it, then run by a small in-process runner. Because the
queue lives in Postgres:

  - a restart or free-tier spin-down no longer loses work — pending jobs run
    when the process comes back, and jobs that were mid-run are retried;
  - several instances can share the queue safely: each claims a job with
    SELECT ... FOR UPDATE SKIP LOCKED, so no job runs twice at once;
  - failures are retried with backoff and the error is kept on the row.

Source uploads still process in FastAPI BackgroundTasks (their file bytes
aren't stored), so on startup any upload stuck mid-processing is marked
failed with a clear message instead of spinning forever.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

import structlog
from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import Job, Sermon

logger = structlog.get_logger()

MAX_ATTEMPTS = 3
RETRY_BACKOFF = (timedelta(seconds=30), timedelta(minutes=5))
STALE_RUNNING_AFTER = timedelta(minutes=15)
STUCK_UPLOAD_AFTER = timedelta(minutes=30)
KEEP_FINISHED_FOR = timedelta(days=7)
POLL_INTERVAL_SECONDS = 15.0

INTERRUPTED_UPLOAD_MESSAGE = "Processing was interrupted when the server restarted. Please upload this file again."


def _handlers() -> dict[str, Callable[..., Awaitable[None]]]:
    # Imported lazily: handlers pull in the AI and embedding stack.
    from app.workers import tasks

    return {
        "extract_voice_dna": tasks.extract_voice_dna_task,
        "index_writing_samples": tasks.index_writing_samples_task,
        "index_testimony": tasks.index_testimony_task,
        "generate_chapter_summary": tasks.generate_chapter_summary_task,
        "index_chapter": tasks.index_chapter_task,
    }


JOB_KINDS = ("extract_voice_dna", "index_writing_samples", "index_testimony", "generate_chapter_summary", "index_chapter")


async def enqueue_job(db: AsyncSession, kind: str, **payload) -> Optional[Job]:
    """Queue a job in the caller's transaction (caller commits, then wake_runner()).

    An identical job that hasn't started yet is reused rather than duplicated —
    saving a chapter ten times queues one re-index, not ten.
    """
    if kind not in JOB_KINDS:
        raise ValueError(f"Unknown job kind: {kind}")
    existing = (await db.execute(
        select(Job).where(Job.kind == kind, Job.status == "pending", Job.payload == payload).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    job = Job(kind=kind, payload=payload, status="pending", attempts=0,
              run_after=datetime.utcnow(), created_at=datetime.utcnow())
    db.add(job)
    return job


async def _claim_next(now: datetime) -> Optional[tuple[str, str, dict, int]]:
    async with AsyncSessionLocal() as db:
        job = (await db.execute(
            select(Job)
            .where(Job.status == "pending", Job.run_after <= now)
            .order_by(Job.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )).scalar_one_or_none()
        if job is None:
            return None
        job.status, job.started_at, job.attempts = "running", now, job.attempts + 1
        await db.commit()
        return job.id, job.kind, dict(job.payload or {}), job.attempts


async def _finish(job_id: str, attempts: int, error: Optional[Exception]) -> None:
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        if error is None:
            values = {"status": "done", "finished_at": now, "last_error": None}
        elif attempts >= MAX_ATTEMPTS:
            values = {"status": "failed", "finished_at": now, "last_error": str(error)[:2000]}
        else:
            backoff = RETRY_BACKOFF[min(attempts - 1, len(RETRY_BACKOFF) - 1)]
            values = {"status": "pending", "run_after": now + backoff, "last_error": str(error)[:2000]}
        await db.execute(update(Job).where(Job.id == job_id).values(**values))
        await db.commit()


async def run_pending(limit: int = 20, handlers: Optional[dict] = None) -> int:
    """Run up to `limit` due jobs, one at a time. Returns how many ran."""
    handlers = handlers or _handlers()
    ran = 0
    while ran < limit:
        claimed = await _claim_next(datetime.utcnow())
        if claimed is None:
            break
        job_id, kind, payload, attempts = claimed
        error: Optional[Exception] = None
        try:
            handler = handlers.get(kind)
            if handler is None:
                raise RuntimeError(f"No handler for job kind {kind!r}")
            await handler(**payload)
        except Exception as exc:  # recorded on the row and retried
            error = exc
            logger.warning("job_failed", job_id=job_id, kind=kind, attempt=attempts, error=str(exc)[:500])
        await _finish(job_id, attempts, error)
        ran += 1
    return ran


async def recover_on_startup(now: Optional[datetime] = None) -> dict:
    """Requeue jobs orphaned mid-run, fail uploads stuck mid-processing, prune old rows."""
    now = now or datetime.utcnow()
    async with AsyncSessionLocal() as db:
        requeued = (await db.execute(
            update(Job)
            .where(Job.status == "running", Job.started_at < now - STALE_RUNNING_AFTER)
            .values(status="pending", run_after=now)
        )).rowcount
        stuck = (await db.execute(
            update(Sermon)
            .where(and_(Sermon.status.in_(("pending", "extracting", "analyzing")), Sermon.created_at < now - STUCK_UPLOAD_AFTER))
            .values(status="failed", error_message=INTERRUPTED_UPLOAD_MESSAGE)
        )).rowcount
        pruned = (await db.execute(
            delete(Job).where(Job.status.in_(("done", "failed")), Job.finished_at < now - KEEP_FINISHED_FOR)
        )).rowcount
        await db.commit()
    result = {"requeued_jobs": requeued, "failed_uploads": stuck, "pruned_jobs": pruned}
    logger.info("jobs_recovered", **result)
    return result


class JobRunner:
    """Polls the queue in the background; wake() runs new work immediately."""

    def __init__(self, poll_interval: float = POLL_INTERVAL_SECONDS):
        self._poll_interval = poll_interval
        self._wake = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def wake(self) -> None:
        self._wake.set()

    async def _loop(self) -> None:
        try:
            await recover_on_startup()
        except Exception:
            logger.exception("job_recovery_failed")
        while True:
            try:
                await run_pending()
            except Exception:
                logger.exception("job_runner_iteration_failed")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                pass
            self._wake.clear()


runner = JobRunner()


def wake_runner() -> None:
    """Call after committing enqueued jobs so they start without waiting for the next poll."""
    runner.wake()
