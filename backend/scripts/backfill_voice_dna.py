"""
One-time backfill: process every VoiceProfile whose Voice DNA never ran.

Why this is needed: before the fix in commit 3f6b4b3, onboarding completion
dispatched voice DNA extraction via Dramatiq, which had no worker/Redis
configured in production — those jobs were enqueued and never executed.
Any author who completed onboarding before that fix deployed has a
VoiceProfile with writing_samples but no voice_summary/signature_phrases/
cadence_score, and will see "still being processed" forever, because
nothing is ever going to pick that job up.

This script finds exactly those profiles and runs extraction + embedding
indexing directly (no background dispatch — runs to completion in this
process), the same logic app/workers/tasks.py now runs automatically for
every NEW signup going forward.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/backfill_voice_dna.py            # process all stuck profiles
    python scripts/backfill_voice_dna.py --dry-run   # show what would run, change nothing
"""
import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import VoiceProfile
from app.services.ai.generation import extract_voice_dna
from app.services.voice.embeddings import index_writing_sample
from app.services.voice.timeline import snapshot_voice


async def find_stuck_profiles(db) -> list[VoiceProfile]:
    """
    A profile is "stuck" if onboarding finished (it has writing_samples,
    meaning onboarding/complete ran) but extraction never populated
    voice_summary.
    """
    result = await db.execute(
        select(VoiceProfile)
        .where(VoiceProfile.writing_samples.isnot(None))
        .where(VoiceProfile.voice_summary.is_(None))
    )
    return list(result.scalars().all())


async def backfill_one(profile: VoiceProfile, db) -> bool:
    print(f"  Processing user_id={profile.user_id} ...", flush=True)

    dna = await extract_voice_dna(profile, db)
    if not dna:
        print(f"    ✗ extraction returned nothing (check ANTHROPIC_API_KEY / LLM_PROVIDER)")
        return False

    profile.signature_phrases = dna.get("signature_phrases", [])
    profile.cadence_score = dna.get("cadence_score", 0.5)
    profile.style_tags = dna.get("style_tags", [])
    profile.voice_summary = dna.get("voice_summary", "")

    existing = {s["ref"]: s for s in (profile.anchor_scriptures or [])}
    for s in dna.get("anchor_scriptures", []):
        if s["ref"] not in existing:
            existing[s["ref"]] = s
    profile.anchor_scriptures = list(existing.values())

    await db.commit()

    await snapshot_voice(
        profile=profile,
        trigger="onboarding_complete",
        db=db,
        change_summary="Initial voice DNA extracted from writing samples (backfilled).",
    )

    indexed = 0
    for sample in profile.writing_samples or []:
        indexed += await index_writing_sample(profile.user_id, sample, db)

    print(f"    ✓ voice_summary set, {len(profile.signature_phrases)} phrases, "
          f"{len(profile.anchor_scriptures)} scriptures, {indexed} sample chunks indexed")
    return True


async def main():
    dry_run = "--dry-run" in sys.argv

    async with AsyncSessionLocal() as db:
        stuck = await find_stuck_profiles(db)

        if not stuck:
            print("No stuck profiles found — nothing to backfill.")
            return

        print(f"Found {len(stuck)} profile(s) with onboarding data but no extracted Voice DNA:")
        for p in stuck:
            sample_count = len(p.writing_samples or [])
            print(f"  - user_id={p.user_id}  ({sample_count} writing sample(s))")

        if dry_run:
            print("\n--dry-run: not processing. Re-run without --dry-run to backfill.")
            return

        print(f"\nProcessing {len(stuck)} profile(s)...\n")
        succeeded = 0
        for profile in stuck:
            try:
                if await backfill_one(profile, db):
                    succeeded += 1
            except Exception as e:
                print(f"    ✗ failed: {e}")

        print(f"\nDone: {succeeded}/{len(stuck)} profiles backfilled successfully.")


if __name__ == "__main__":
    asyncio.run(main())
