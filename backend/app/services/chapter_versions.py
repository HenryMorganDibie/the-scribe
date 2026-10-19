"""
Chapter draft history.

Versions are taken:
  - while the author writes: before an edit overwrites the chapter, at most
    once per AUTOSAVE_INTERVAL (autosave fires every ~2s, so every save would
    bury real history under near-duplicates);
  - always before AI generation replaces the chapter ("before_ai");
  - always before a restore replaces it ("before_restore"), so a restore can
    itself be undone.

Only the newest MAX_VERSIONS per chapter are kept.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, ChapterVersion

AUTOSAVE_INTERVAL = timedelta(minutes=10)
MAX_VERSIONS = 50


def _is_blank(html: Optional[str]) -> bool:
    return not html or html.strip() in ("", "<p></p>")


async def snapshot_chapter(
    db: AsyncSession,
    chapter: Chapter,
    reason: str,
    *,
    min_interval: Optional[timedelta] = None,
) -> Optional[ChapterVersion]:
    """Save the chapter's *current* content as a version. Adds to the session; caller commits.

    Skips blank chapters, content identical to the newest version, and — when
    `min_interval` is given — anything within that interval of the newest version.
    """
    if _is_blank(chapter.content):
        return None

    latest = (await db.execute(
        select(ChapterVersion)
        .where(ChapterVersion.chapter_id == chapter.id)
        .order_by(ChapterVersion.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    if latest is not None:
        if latest.content == chapter.content:
            return None
        if min_interval is not None and datetime.utcnow() - latest.created_at < min_interval:
            return None

    version = ChapterVersion(
        chapter_id=chapter.id,
        user_id=chapter.user_id,
        content=chapter.content,
        word_count=chapter.word_count or 0,
        reason=reason,
        created_at=datetime.utcnow(),
    )
    db.add(version)
    await db.flush()
    await _prune(db, chapter.id)
    return version


async def _prune(db: AsyncSession, chapter_id: str) -> None:
    keep = select(ChapterVersion.id).where(ChapterVersion.chapter_id == chapter_id) \
        .order_by(ChapterVersion.created_at.desc()).limit(MAX_VERSIONS)
    await db.execute(
        delete(ChapterVersion).where(
            ChapterVersion.chapter_id == chapter_id,
            ChapterVersion.id.not_in(keep.scalar_subquery()),
        )
    )
