"""
In-process background tasks for FastAPI's BackgroundTasks.

These run as plain async functions, scheduled via BackgroundTasks.add_task()
from the request that triggers them (see app/api/routes/onboarding.py,
projects.py, voice.py). They execute in the same process, after the response
has been sent — there is no separate worker process and no message broker.

Why not Dramatiq/Redis: this app deploys on a single web service (Render
free/starter tier) with no Redis instance and no worker process configured.
Dramatiq actors with no running worker silently never execute — which is
exactly what was happening here: voice DNA extraction, writing-sample
indexing, and chapter summaries were enqueued but never processed for any
production signup, because nothing was ever connected to consume the queue.

This mirrors app/services/ingestion/pipeline.py's process_sermon, which
already uses this exact pattern successfully (see app/api/routes/sermons.py).

Scaling note: in-process background tasks run on the same request-handling
process, sharing its CPU/memory. For a few thousand concurrent users this is
fine -- each task is a handful of LLM calls + embedding/DB writes (seconds,
not minutes), and Render can scale the web service horizontally (more
instances) if needed. If sustained background-task volume ever becomes large
enough to starve request handling, the next step is a dedicated worker
service + queue (Redis/Dramatiq, or Render's own background worker service
type) -- not a route-level concern, so call sites do not need to change when
that day comes.
"""
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import VoiceProfile, Chapter
from app.services.ai.generation import extract_voice_dna, generate_chapter_summary
from app.services.voice.embeddings import index_writing_sample, index_testimony, index_chapter, embedding_service
from app.services.voice.timeline import snapshot_voice

import structlog

logger = structlog.get_logger()


async def extract_voice_dna_task(user_id: str) -> None:
    """
    Extract voice DNA from writing samples after onboarding.
    Typically 5-20s depending on sample size and LLM provider.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VoiceProfile).where(VoiceProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                return

            dna = await extract_voice_dna(profile, db)
            if dna:
                profile.signature_phrases = dna.get("signature_phrases", [])
                profile.cadence_score = dna.get("cadence_score", 0.5)
                profile.style_tags = dna.get("style_tags", [])
                profile.voice_summary = dna.get("voice_summary", "")

                # Merge anchor scriptures (additive — never drop existing ones)
                existing = {s["ref"]: s for s in (profile.anchor_scriptures or [])}
                for s in dna.get("anchor_scriptures", []):
                    if s["ref"] not in existing:
                        existing[s["ref"]] = s
                profile.anchor_scriptures = list(existing.values())

                # Cache the voice summary embedding
                if profile.voice_summary:
                    profile.voice_summary_embedding = await embedding_service.embed(profile.voice_summary)

                await db.commit()

                await snapshot_voice(
                    profile=profile,
                    trigger="onboarding_complete",
                    db=db,
                    change_summary="Initial voice DNA extracted from writing samples.",
                )
    except Exception:
        logger.exception("extract_voice_dna_task_failed", user_id=user_id)


async def index_writing_samples_task(user_id: str) -> None:
    """Index all writing samples for a user into pgvector."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VoiceProfile).where(VoiceProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile or not profile.writing_samples:
                return

            from sqlalchemy import delete
            from app.models import DocumentEmbedding
            await db.execute(
                delete(DocumentEmbedding).where(
                    DocumentEmbedding.user_id == user_id,
                    DocumentEmbedding.doc_type == "writing_sample"
                )
            )

            for sample in profile.writing_samples:
                await index_writing_sample(user_id, sample, db)
    except Exception:
        logger.exception("index_writing_samples_task_failed", user_id=user_id)


async def index_testimony_task(user_id: str, testimony_id: str, story: str) -> None:
    """Index a single testimony into pgvector for retrieval."""
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import delete
            from app.models import DocumentEmbedding
            await db.execute(
                delete(DocumentEmbedding).where(
                    DocumentEmbedding.user_id == user_id,
                    DocumentEmbedding.doc_type == "testimony",
                    DocumentEmbedding.source_id == testimony_id
                )
            )
            await index_testimony(user_id, testimony_id, story, db)
    except Exception:
        logger.exception("index_testimony_task_failed", user_id=user_id, testimony_id=testimony_id)


async def generate_chapter_summary_task(chapter_id: str) -> None:
    """Generate and store a chapter summary after content is saved."""
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
            chapter = result.scalar_one_or_none()
            if not chapter or not chapter.content:
                return

            summary = await generate_chapter_summary(chapter.content, chapter.title)
            chapter.summary = summary
            await db.commit()
    except Exception:
        logger.exception("generate_chapter_summary_task_failed", chapter_id=chapter_id)


async def index_chapter_task(chapter_id: str) -> None:
    """
    Re-index a chapter's content into pgvector for Manuscript Companion Chat
    retrieval. Runs independently of generate_chapter_summary_task (separate
    failure domains -- a broken summary shouldn't block retrieval indexing
    and vice versa) whenever chapter content is saved.
    """
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
            chapter = result.scalar_one_or_none()
            if not chapter:
                return

            await index_chapter(chapter.user_id, chapter.project_id, chapter.id, chapter.content, db)
    except Exception:
        logger.exception("index_chapter_task_failed", chapter_id=chapter_id)
