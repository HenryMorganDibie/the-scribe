"""
Shared helper for scheduling in-process background work from API routes.

Background tasks (voice DNA extraction, embedding indexing, chapter
summaries) run via FastAPI's BackgroundTasks: scheduled during the request,
executed in the same process after the response has been sent. There is no
external broker (Redis) or worker process — see app/workers/tasks.py for the
full rationale.

fire_background_job wraps BackgroundTasks.add_task purely for consistent
logging at the call sites (so every background dispatch logs the same way,
and a bad call here can't take down the request that scheduled it).
"""
from typing import Any, Callable, Coroutine
import structlog

from fastapi import BackgroundTasks

logger = structlog.get_logger()


def fire_background_job(
    background_tasks: BackgroundTasks,
    task: Callable[..., Coroutine],
    *args: Any,
    job_name: str | None = None,
    **kwargs: Any,
) -> bool:
    """
    Schedule an async task to run after the current request's response is
    sent. Returns True if scheduling succeeded, False otherwise (logged
    either way; scheduling failures do not raise, so the calling request
    still succeeds).
    """
    name = job_name or getattr(task, "__name__", str(task))
    try:
        background_tasks.add_task(task, *args, **kwargs)
        logger.debug("background_job_scheduled", job=name)
        return True
    except Exception as e:
        logger.warning("background_job_schedule_failed", job=name, error=str(e))
        return False
