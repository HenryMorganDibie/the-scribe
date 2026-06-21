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

Two reliability fixes baked in (learned from the first real run):
1. The embedding model (fastembed/ONNX, ~90MB) is pre-warmed BEFORE any
   database session is opened. On a cold cache this download can take
   several minutes; if a DB connection (especially Supabase's pooler) sits
   idle that whole time, the pooler drops it, and the next query fails with
   "connection is closed". Pre-warming means no connection is ever left
   idle waiting on a slow download.
2. Each profile gets its OWN fresh database session. SQLAlchemy poisons a
   session after any failed flush — reusing one session across all profiles
   meant a single mid-run failure cascaded into every subsequent profile
   failing immediately too, even though the cause had nothing to do with
   them. One profile's failure can no longer affect any other's.

Usage:
    cd backend
    source venv/bin/activate
    python -m scripts.backfill_voice_dna             # process all stuck profiles
    python -m scripts.backfill_voice_dna --dry-run    # show what would run, change nothing

Safe to re-run: profiles with voice_summary already set are excluded by the
query, so already-fixed users are skipped automatically.
"""
import asyncio
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import VoiceProfile
from app.services.ai.generation import extract_voice_dna
from app.services.voice.embeddings import embedding_service, index_writing_sample
from app.services.voice.timeline import snapshot_voice


async def find_stuck_user_ids(db) -> list[str]:
    """
    A profile is "stuck" if onboarding finished (it has writing_samples,
    meaning onboarding/complete ran) but extraction never populated
    voice_summary. Returns user_ids only — each profile is re-fetched in
    its own fresh session later, so we don't hold ORM objects across
    sessions.
    """
    result = await db.execute(
        select(VoiceProfile.user_id, VoiceProfile.writing_samples)
        .where(VoiceProfile.writing_samples.isnot(None))
        .where(VoiceProfile.voice_summary.is_(None))
    )
    return result.all()


async def backfill_one(user_id: str) -> bool:
    """
    Runs entirely against a single, fresh session — if this fails, it
    cannot affect any other profile's session.
    """
    print(f"  Processing user_id={user_id} ...", flush=True)

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == user_id))
            profile = result.scalar_one_or_none()
            if not profile:
                print("    ✗ profile vanished between scan and processing — skipping")
                return False

            dna = await extract_voice_dna(profile, db)
            if not dna:
                print("    ✗ extraction returned nothing (check ANTHROPIC_API_KEY / LLM_PROVIDER)")
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
                indexed += await index_writing_sample(user_id, sample, db)

            print(f"    ✓ voice_summary set, {len(profile.signature_phrases)} phrases, "
                  f"{len(profile.anchor_scriptures)} scriptures, {indexed} sample chunks indexed")
            return True

        except Exception as e:
            print(f"    ✗ failed: {e}")
            await db.rollback()
            return False


async def main():
    dry_run = "--dry-run" in sys.argv

    async with AsyncSessionLocal() as scan_db:
        rows = await find_stuck_user_ids(scan_db)

    if not rows:
        print("No stuck profiles found — nothing to backfill.")
        return

    print(f"Found {len(rows)} profile(s) with onboarding data but no extracted Voice DNA:")
    for user_id, samples in rows:
        print(f"  - user_id={user_id}  ({len(samples or [])} writing sample(s))")

    if dry_run:
        print("\n--dry-run: not processing. Re-run without --dry-run to backfill.")
        return

    # Pre-warm the embedding model ONCE, up front, before opening any DB
    # session for the actual backfill work — see module docstring point 1.
    print("\nPre-loading embedding model (first run may take a few minutes to download)...", flush=True)
    await embedding_service.embed("warmup")
    print("Embedding model ready.\n", flush=True)

    print(f"Processing {len(rows)} profile(s)...\n")
    succeeded = 0
    for user_id, _samples in rows:
        if await backfill_one(user_id):
            succeeded += 1

    print(f"\nDone: {succeeded}/{len(rows)} profiles backfilled successfully.")
    if succeeded < len(rows):
        print("Re-run the same command — already-succeeded profiles are skipped automatically.")


if __name__ == "__main__":
    asyncio.run(main())
