"""
Shared scripture-reference verification against the real `Scripture` index.

Used everywhere the LLM proposes a Bible reference (`/scripture-suggest`,
voice-DNA anchor-scripture extraction in generation.py/voice_enrichment.py)
so a reference is only ever trusted once it resolves to a real, stored
verse, never taken on the model's word alone.
"""
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scripture

_REF_RE = re.compile(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?$")


async def _lookup(ref: str, db: AsyncSession) -> Optional[Scripture]:
    """
    Resolve a reference string to its Scripture row. Tries an exact match
    first (covers curated ranges like "Isaiah 61:1-3"), then falls back to
    book+chapter+verse_start (covers a range the LLM proposed that only
    exists per-verse in the bulk-seeded KJV table).
    """
    ref = ref.strip()
    row = (await db.execute(select(Scripture).where(Scripture.reference == ref))).scalar_one_or_none()
    if row is not None:
        return row

    m = _REF_RE.match(ref)
    if not m:
        return None
    book, chapter, verse_start = m.group(1), int(m.group(2)), int(m.group(3))
    return (
        await db.execute(
            select(Scripture).where(
                Scripture.book == book,
                Scripture.chapter == chapter,
                Scripture.verse_start == verse_start,
            )
        )
    ).scalar_one_or_none()


async def resolve_scripture_ref(ref: str, db: AsyncSession) -> Optional[str]:
    """Confirm `ref` resolves to a real verse; return its canonical
    `reference` column value if so, else None."""
    row = await _lookup(ref, db)
    return row.reference if row is not None else None


async def filter_verified_anchor_scriptures(anchor_scriptures: Optional[list], db: AsyncSession) -> list:
    """
    Given a list of LLM-proposed {"ref": ..., "themes": [...]} dicts (voice-DNA
    anchor-scripture extraction), keep only entries whose ref resolves to a
    real verse, normalized to the canonical reference string. A "hallucinated"
    ref here means the LLM invented a citation that isn't actually in the
    source transcript at all -- a different failure mode than /scripture-suggest
    misquoting a real verse, but the same underlying "verify before storing"
    fix. Malformed entries and unresolvable references are silently dropped.
    """
    verified = []
    for s in anchor_scriptures or []:
        if not isinstance(s, dict) or not s.get("ref"):
            continue
        canonical = await resolve_scripture_ref(s["ref"], db)
        if canonical is None:
            continue
        verified.append({**s, "ref": canonical})
    return verified


async def fetch_scripture_text(ref: str, translation: str, db: AsyncSession) -> Optional[dict]:
    """Like resolve_scripture_ref, but also returns the verified verse text
    in the requested translation (falling back to whichever translation is
    actually populated). Returns None if `ref` doesn't resolve to anything real."""
    row = await _lookup(ref, db)
    if row is None:
        return None

    text = row.text_nkjv if translation.upper() == "NKJV" else None
    text = text or row.text_nkjv or row.text_kjv or row.text_niv or row.text_esv
    if not text:
        return None

    return {"ref": row.reference, "text": text}
