"""Finishing tools: progress and pace, what's next, repetition scan, consistency check."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ownership import get_owned_chapter, get_owned_project
from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.consistency import check_chapter_against_bible, find_repeated_passages
from app.services.progress import STAGE_LABELS, load_progress
from app.services.security.rate_limits import consume_user_quota

router = APIRouter(tags=["progress"])


@router.get("/projects/{project_id}/progress")
async def project_progress(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await get_owned_project(project_id, current_user.id, db)
    progress, steps = await load_progress(db, project)
    return {**progress, "stage_labels": STAGE_LABELS, "next_steps": steps}


@router.get("/projects/{project_id}/repetition")
async def repeated_passages(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_owned_project(project_id, current_user.id, db)
    return {"pairs": await find_repeated_passages(db, project_id)}


@router.post("/projects/{project_id}/chapters/{chapter_id}/consistency-check")
async def consistency_check(project_id: str, chapter_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await get_owned_project(project_id, current_user.id, db)
    chapter = await get_owned_chapter(chapter_id, current_user.id, db, project_id=project_id)
    if not (chapter.content or "").strip():
        raise HTTPException(status_code=400, detail="Write something in this chapter first.")
    await consume_user_quota(db, current_user.id, "ai_request", settings.AI_DAILY_REQUEST_LIMIT)
    return await check_chapter_against_bible(db, project, chapter)
