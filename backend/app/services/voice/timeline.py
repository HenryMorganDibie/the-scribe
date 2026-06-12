"""
Voice Evolution Timeline service.
Snapshots the author's voice profile like git commits —
tracks how their voice changes and learns from accepted edits over time.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import VoiceProfile, VoiceVersion


async def snapshot_voice(
    profile: VoiceProfile,
    trigger: str,
    db: AsyncSession,
    chapter_id: Optional[str] = None,
    change_summary: Optional[str] = None,
) -> VoiceVersion:
    """
    Create a new voice version snapshot.
    Called after: onboarding complete, user edits accepted, manual profile update.
    """
    # Get next version number
    result = await db.execute(
        select(func.max(VoiceVersion.version_number))
        .where(VoiceVersion.user_id == profile.user_id)
    )
    max_version = result.scalar() or 0
    next_version = max_version + 1

    snapshot = {
        "theological_lens": profile.theological_lens,
        "signature_phrases": profile.signature_phrases or [],
        "anchor_scriptures": profile.anchor_scriptures or [],
        "cadence_score": profile.cadence_score,
        "style_tags": profile.style_tags or [],
        "voice_summary": profile.voice_summary,
        "tone_preferences": profile.tone_preferences or [],
        "snapshotted_at": datetime.utcnow().isoformat(),
    }

    version = VoiceVersion(
        user_id=profile.user_id,
        version_number=next_version,
        snapshot=snapshot,
        trigger=trigger,
        change_summary=change_summary,
        chapter_id=chapter_id,
        cadence_score=profile.cadence_score,
        phrase_count=len(profile.signature_phrases or []),
        scripture_count=len(profile.anchor_scriptures or []),
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def get_timeline(user_id: str, db: AsyncSession) -> list:
    """Retrieve all voice versions for a user, most recent first."""
    result = await db.execute(
        select(VoiceVersion)
        .where(VoiceVersion.user_id == user_id)
        .order_by(VoiceVersion.version_number.desc())
    )
    return result.scalars().all()


async def diff_versions(v1: VoiceVersion, v2: VoiceVersion) -> dict:
    """
    Compute a human-readable diff between two voice versions.
    Used in the Voice Evolution Timeline UI.
    """
    s1 = v1.snapshot
    s2 = v2.snapshot

    added_phrases = set(s2.get("signature_phrases", [])) - set(s1.get("signature_phrases", []))
    removed_phrases = set(s1.get("signature_phrases", [])) - set(s2.get("signature_phrases", []))
    cadence_delta = (s2.get("cadence_score") or 0) - (s1.get("cadence_score") or 0)

    return {
        "version_from": v1.version_number,
        "version_to": v2.version_number,
        "added_phrases": list(added_phrases),
        "removed_phrases": list(removed_phrases),
        "cadence_delta": round(cadence_delta, 3),
        "cadence_direction": "more flowing" if cadence_delta > 0 else "more punchy" if cadence_delta < 0 else "unchanged",
        "scripture_count_delta": (v2.scripture_count or 0) - (v1.scripture_count or 0),
    }
