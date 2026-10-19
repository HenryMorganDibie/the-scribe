"""Durable background jobs against a real Postgres.

Skipped unless TEST_DATABASE_URL is set (see tests/test_delete_integration.py).
The job runner opens its own sessions, so `jobs.AsyncSessionLocal` is pointed
at the disposable test database — never at the app's configured DATABASE_URL.
"""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.routes import projects
from app.core.config import normalize_db_url
from app.models import Job, Sermon, User
from app.services import jobs
from tests.test_workspace_integration import (  # noqa: F401 — fixtures are used by name
    TEST_DATABASE_URL, _seed, db, fake_embeddings, migrated_database,
)

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture(autouse=True)
async def jobs_use_test_database(monkeypatch, db):
    engine = create_async_engine(
        normalize_db_url(TEST_DATABASE_URL), poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    monkeypatch.setattr(jobs, "AsyncSessionLocal", async_sessionmaker(engine, expire_on_commit=False))
    # Start each test from an empty queue.
    await db.execute(Job.__table__.delete())
    await db.commit()
    yield
    await engine.dispose()


async def _jobs(db):
    db.expire_all()
    return (await db.execute(select(Job).order_by(Job.created_at))).scalars().all()


async def test_saving_a_chapter_queues_one_summary_and_one_reindex_however_often_you_save(db):
    s = await _seed(db)
    chapter_id = s.chapter.id
    for text in ("<p>One.</p>", "<p>Two.</p>", "<p>Three.</p>"):
        await projects.update_chapter(
            s.project.id, s.chapter.id, projects.ChapterUpdate(content=text, trigger_indexing=True),
            current_user=s.user, db=db,
        )
    queued = await _jobs(db)
    assert sorted(j.kind for j in queued) == ["generate_chapter_summary", "index_chapter"]
    assert all(j.status == "pending" and j.payload == {"chapter_id": chapter_id} for j in queued)


async def test_runner_runs_jobs_and_marks_them_done(db):
    calls = []

    async def handler(chapter_id):
        calls.append(chapter_id)

    await jobs.enqueue_job(db, "index_chapter", chapter_id="c1")
    await jobs.enqueue_job(db, "index_chapter", chapter_id="c2")
    await db.commit()

    ran = await jobs.run_pending(handlers={"index_chapter": handler})

    assert ran == 2 and calls == ["c1", "c2"]
    assert [(j.status, j.attempts) for j in await _jobs(db)] == [("done", 1), ("done", 1)]


async def test_failures_are_retried_with_backoff_then_marked_failed(db, monkeypatch):
    async def broken(chapter_id):
        raise RuntimeError("embedding service down")

    await jobs.enqueue_job(db, "index_chapter", chapter_id="c1")
    await db.commit()

    await jobs.run_pending(handlers={"index_chapter": broken})
    job = (await _jobs(db))[0]
    assert (job.status, job.attempts, job.last_error) == ("pending", 1, "embedding service down")
    assert job.run_after > datetime.utcnow()  # backing off, not immediately retried
    assert await jobs.run_pending(handlers={"index_chapter": broken}) == 0

    # Fast-forward through the remaining attempts.
    for _ in range(jobs.MAX_ATTEMPTS - 1):
        await db.execute(Job.__table__.update().values(run_after=datetime.utcnow() - timedelta(seconds=1)))
        await db.commit()
        await jobs.run_pending(handlers={"index_chapter": broken})

    job = (await _jobs(db))[0]
    assert (job.status, job.attempts) == ("failed", jobs.MAX_ATTEMPTS)


async def test_startup_recovery_requeues_orphans_and_fails_stuck_uploads(db):
    now = datetime.utcnow()
    db.add_all([
        Job(kind="index_chapter", payload={"chapter_id": "old"}, status="running", attempts=1,
            run_after=now, created_at=now, started_at=now - timedelta(hours=1)),
        Job(kind="index_chapter", payload={"chapter_id": "live"}, status="running", attempts=1,
            run_after=now, created_at=now, started_at=now - timedelta(minutes=1)),
        Job(kind="index_chapter", payload={"chapter_id": "ancient"}, status="done", attempts=1,
            run_after=now, created_at=now, finished_at=now - timedelta(days=30)),
    ])
    user = User(email=f"{uuid.uuid4().hex}@example.com", hashed_password="x")
    db.add(user)
    await db.flush()
    stuck = Sermon(user_id=user.id, title="Stuck", source_type="pdf", status="extracting", created_at=now - timedelta(hours=2))
    fresh = Sermon(user_id=user.id, title="Fresh", source_type="pdf", status="extracting", created_at=now)
    db.add_all([stuck, fresh])
    await db.commit()
    stuck_id, fresh_id = stuck.id, fresh.id

    result = await jobs.recover_on_startup(now)

    assert result == {"requeued_jobs": 1, "failed_uploads": 1, "pruned_jobs": 1}
    statuses = {j.payload["chapter_id"]: j.status for j in await _jobs(db)}
    assert statuses == {"old": "pending", "live": "running"}
    upload_status = dict((await db.execute(select(Sermon.id, Sermon.status).where(Sermon.id.in_([stuck_id, fresh_id])))).all())
    assert upload_status == {stuck_id: "failed", fresh_id: "extracting"}


async def test_unknown_job_kinds_are_rejected(db):
    with pytest.raises(ValueError):
        await jobs.enqueue_job(db, "drop_tables")
