"""
Shared utilities for dispatching Dramatiq background jobs from API routes.

Background jobs (voice DNA extraction, embedding indexing, chapter summaries)
are non-blocking: if Redis/Dramatiq isn't running, the API request still
succeeds — the job is simply never enqueued. This is intentional for local
development without Redis, but failures are logged (not silently swallowed)
so they're visible in production.
"""
from typing import Any, Callable
import structlog

logger = structlog.get_logger()


def fire_background_job(actor: Callable, *args: Any, job_name: str | None = None, **kwargs: Any) -> bool:
    """
    Enqueue a Dramatiq actor without letting a broker failure break the
    calling request.

    Returns True if the job was enqueued, False if it failed (logged either way).
    """
    name = job_name or getattr(actor, "actor_name", str(actor))
    try:
        actor.send(*args, **kwargs)
        logger.debug("background_job_enqueued", job=name)
        return True
    except Exception as e:
        logger.warning(
            "background_job_enqueue_failed",
            job=name,
            error=str(e),
            hint="Is Redis running and DRAMATIQ broker reachable? "
                 "The request still succeeded — this job will not run until "
                 "it is retried or the worker comes back online.",
        )
        return False
