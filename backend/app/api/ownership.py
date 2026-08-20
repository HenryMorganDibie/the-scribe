"""Tenant ownership lookups shared by API routes.

Always return 404 for missing and foreign resources so callers cannot use the
API to discover whether another user's object exists.
"""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, Project


async def get_owned_project(
    project_id: str,
    user_id: str,
    db: AsyncSession,
) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def get_owned_chapter(
    chapter_id: str,
    user_id: str,
    db: AsyncSession,
    *,
    project_id: Optional[str] = None,
) -> Chapter:
    conditions = [
        Chapter.id == chapter_id,
        Chapter.user_id == user_id,
    ]
    if project_id is not None:
        conditions.append(Chapter.project_id == project_id)

    result = await db.execute(select(Chapter).where(*conditions))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter
