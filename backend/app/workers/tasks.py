"""
Background job handlers.

Each handler is a plain async function that takes only IDs, loads what it
needs, and RAISES on failure — app/services/jobs.py records the error and
retries. Jobs are queued in the `jobs` table (enqueue_job), so they survive
restarts and the free-tier spin-downs that silently killed the old in-process
BackgroundTasks.

Handlers must be safe to run twice (a job can be retried after a crash
mid-way): each one re-derives its result from the current database state.
"""
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.models import Chapter, DocumentEmbedding, Testimony, VoiceProfile
from app.services.ai.generation import extract_voice_dna, generate_chapter_summary
from app.services.voice.embeddings import embedding_service, index_chapter, index_testimony, index_writing_sample
from app.services.voice.timeline import snapshot_voice


async def extract_voice_dna_task(user_id: str) -> None:
    """Extract voice DNA from the author's writing samples (5–20s, one AI call)."""
    async with AsyncSessionLocal() as db:
        profile = (await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == user_id))).scalar_one_or_none()
        if not profile:
            return

        dna = await extract_voice_dna(profile, db)
        if not dna:
            raise RuntimeError("Voice DNA extraction returned nothing usable")

        profile.signature_phrases = dna.get("signature_phrases", [])
        profile.cadence_score = dna.get("cadence_score", 0.5)
        profile.style_tags = dna.get("style_tags", [])
        profile.voice_summary = dna.get("voice_summary", "")

        # Merge anchor scriptures (additive — never drop existing ones)
        existing = {s["ref"]: s for s in (profile.anchor_scriptures or []) if isinstance(s, dict) and "ref" in s}
        for s in dna.get("anchor_scriptures", []):
            if isinstance(s, dict) and s.get("ref") and s["ref"] not in existing:
                existing[s["ref"]] = s
        profile.anchor_scriptures = list(existing.values())

        if profile.voice_summary:
            profile.voice_summary_embedding = await embedding_service.embed(profile.voice_summary)
        await db.commit()

        await snapshot_voice(
            profile=profile, trigger="onboarding_complete", db=db,
            change_summary="Voice DNA extracted from writing samples.",
        )


async def index_writing_samples_task(user_id: str) -> None:
    """Re-index all of the author's writing samples into pgvector."""
    async with AsyncSessionLocal() as db:
        profile = (await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == user_id))).scalar_one_or_none()
        if not profile or not profile.writing_samples:
            return
        await db.execute(delete(DocumentEmbedding).where(
            DocumentEmbedding.user_id == user_id, DocumentEmbedding.doc_type == "writing_sample",
        ))
        for sample in profile.writing_samples:
            await index_writing_sample(user_id, sample, db)


async def index_testimony_task(user_id: str, testimony_id: str) -> None:
    """(Re-)index one testimony/story. Reads the current text, so edits are picked up."""
    async with AsyncSessionLocal() as db:
        testimony = (await db.execute(
            select(Testimony).where(Testimony.id == testimony_id, Testimony.user_id == user_id)
        )).scalar_one_or_none()
        await db.execute(delete(DocumentEmbedding).where(
            DocumentEmbedding.user_id == user_id,
            DocumentEmbedding.doc_type == "testimony",
            DocumentEmbedding.source_id == testimony_id,
        ))
        if testimony is None:
            await db.commit()
            return
        await index_testimony(user_id, testimony_id, testimony.story, db)


async def generate_chapter_summary_task(chapter_id: str) -> None:
    """Summarise a chapter for chapter memory (one AI call)."""
    async with AsyncSessionLocal() as db:
        chapter = (await db.execute(select(Chapter).where(Chapter.id == chapter_id))).scalar_one_or_none()
        if not chapter or not chapter.content:
            return
        chapter.summary = await generate_chapter_summary(chapter.content, chapter.title)
        await db.commit()


async def index_chapter_task(chapter_id: str) -> None:
    """Re-index a chapter's content for Companion Chat and repetition checks."""
    async with AsyncSessionLocal() as db:
        chapter = (await db.execute(select(Chapter).where(Chapter.id == chapter_id))).scalar_one_or_none()
        if not chapter:
            return
        await index_chapter(chapter.user_id, chapter.project_id, chapter.id, chapter.content, db)
