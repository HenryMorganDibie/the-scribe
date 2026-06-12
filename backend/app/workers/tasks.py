"""
Dramatiq background workers for long-running tasks:
- Voice DNA extraction (after onboarding)
- Writing sample indexing (embedding ingestion)
- Chapter summary generation
- Voice version snapshots
"""
import dramatiq
from dramatiq.brokers.redis import RedisBroker

from app.core.config import settings

broker = RedisBroker(url=settings.REDIS_URL)
dramatiq.set_broker(broker)


@dramatiq.actor(queue_name="voice_extraction", max_retries=3)
def extract_voice_dna_task(user_id: str):
    """
    Extract voice DNA from writing samples after onboarding.
    Runs in background — can take 10-30s depending on sample size.
    """
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.models import VoiceProfile
    from app.services.ai.generation import extract_voice_dna
    from app.services.voice.timeline import snapshot_voice
    from sqlalchemy import select

    async def _run():
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

                # Merge anchor scriptures
                existing = {s["ref"]: s for s in (profile.anchor_scriptures or [])}
                for s in dna.get("anchor_scriptures", []):
                    if s["ref"] not in existing:
                        existing[s["ref"]] = s
                profile.anchor_scriptures = list(existing.values())

                await db.commit()

                # Snapshot voice version
                await snapshot_voice(
                    profile=profile,
                    trigger="onboarding_complete",
                    db=db,
                    change_summary="Initial voice DNA extracted from writing samples.",
                )

    asyncio.run(_run())


@dramatiq.actor(queue_name="embeddings", max_retries=3)
def index_writing_samples_task(user_id: str):
    """Index all writing samples for a user into pgvector."""
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.models import VoiceProfile
    from app.services.voice.embeddings import index_writing_sample
    from sqlalchemy import select

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(VoiceProfile).where(VoiceProfile.user_id == user_id)
            )
            profile = result.scalar_one_or_none()
            if not profile or not profile.writing_samples:
                return

            for sample in profile.writing_samples:
                await index_writing_sample(user_id, sample, db)

    asyncio.run(_run())


@dramatiq.actor(queue_name="chapter_ops", max_retries=2)
def generate_chapter_summary_task(chapter_id: str):
    """Generate and store a chapter summary after content is saved."""
    import asyncio
    from app.db.session import AsyncSessionLocal
    from app.models import Chapter
    from app.services.ai.generation import generate_chapter_summary
    from sqlalchemy import select

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
            chapter = result.scalar_one_or_none()
            if not chapter or not chapter.content:
                return

            summary = await generate_chapter_summary(chapter.content, chapter.title)
            chapter.summary = summary
            await db.commit()

    asyncio.run(_run())
