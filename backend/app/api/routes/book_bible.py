"""Book bible CRUD: per-book characters, places, terms, sources, notes and research."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ownership import get_owned_chapter, get_owned_project
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import BookEntry, User
from app.services.book_bible import index_entry, remove_entry_index

router = APIRouter(tags=["book-bible"])

EntryKind = Literal["character", "place", "term", "source", "note", "research"]
MAX_ENTRIES_PER_BOOK = 500


class EntryCreate(BaseModel):
    kind: EntryKind
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=20_000)
    chapter_id: Optional[str] = None


class EntryUpdate(BaseModel):
    kind: Optional[EntryKind] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=20_000)
    chapter_id: Optional[str] = None
    detach_chapter: bool = False  # chapter_id=None means "unchanged"; this clears it


def _serialize(e: BookEntry) -> dict:
    return {
        "id": e.id, "kind": e.kind, "title": e.title, "body": e.body, "chapter_id": e.chapter_id,
        "created_at": e.created_at, "updated_at": e.updated_at,
    }


async def _get_owned_entry(entry_id: str, project_id: str, user_id: str, db: AsyncSession) -> BookEntry:
    entry = (await db.execute(
        select(BookEntry).where(
            BookEntry.id == entry_id, BookEntry.project_id == project_id, BookEntry.user_id == user_id,
        )
    )).scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.get("/projects/{project_id}/bible")
async def list_entries(
    project_id: str,
    kind: Optional[EntryKind] = None,
    chapter_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_project(project_id, current_user.id, db)
    conditions = [BookEntry.project_id == project_id, BookEntry.user_id == current_user.id]
    if kind:
        conditions.append(BookEntry.kind == kind)
    if chapter_id:
        conditions.append(BookEntry.chapter_id == chapter_id)
    result = await db.execute(select(BookEntry).where(*conditions).order_by(BookEntry.kind, BookEntry.title))
    return [_serialize(e) for e in result.scalars().all()]


@router.post("/projects/{project_id}/bible", status_code=201)
async def create_entry(
    project_id: str,
    body: EntryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_project(project_id, current_user.id, db)
    if body.chapter_id:
        await get_owned_chapter(body.chapter_id, current_user.id, db, project_id=project_id)
    count = (await db.execute(
        select(func.count(BookEntry.id)).where(BookEntry.project_id == project_id)
    )).scalar_one()
    if count >= MAX_ENTRIES_PER_BOOK:
        raise HTTPException(status_code=400, detail=f"A book can have at most {MAX_ENTRIES_PER_BOOK} entries")

    entry = BookEntry(
        project_id=project_id, user_id=current_user.id, chapter_id=body.chapter_id,
        kind=body.kind, title=body.title.strip(), body=body.body.strip(),
    )
    db.add(entry)
    await db.flush()
    await index_entry(db, entry)
    await db.commit()
    await db.refresh(entry)
    return _serialize(entry)


@router.put("/projects/{project_id}/bible/{entry_id}")
async def update_entry(
    project_id: str,
    entry_id: str,
    body: EntryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned_entry(entry_id, project_id, current_user.id, db)
    if body.chapter_id:
        await get_owned_chapter(body.chapter_id, current_user.id, db, project_id=project_id)
        entry.chapter_id = body.chapter_id
    elif body.detach_chapter:
        entry.chapter_id = None
    if body.kind is not None:
        entry.kind = body.kind
    if body.title is not None:
        entry.title = body.title.strip()
    if body.body is not None:
        entry.body = body.body.strip()

    await index_entry(db, entry)
    await db.commit()
    await db.refresh(entry)
    return _serialize(entry)


@router.delete("/projects/{project_id}/bible/{entry_id}", status_code=204)
async def delete_entry(
    project_id: str,
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    entry = await _get_owned_entry(entry_id, project_id, current_user.id, db)
    await remove_entry_index(db, entry.id)
    await db.delete(entry)
    await db.commit()
