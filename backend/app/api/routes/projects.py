import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models import User, Project, Chapter
from app.core.security import get_current_user
from app.utils.jobs import fire_background_job
from app.services.ai.companion_chat import companion_chat_stream, save_message, get_history

router = APIRouter(tags=["projects"])


# ── Projects ──────────────────────────────────

class ProjectCreate(BaseModel):
    title: str
    genre: Optional[str] = "teaching"
    theme: Optional[str] = None
    target_chapters: Optional[int] = 10


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    theme: Optional[str] = None
    target_chapters: Optional[int] = None
    status: Optional[str] = None


@router.get("/projects")
async def list_projects(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.user_id == current_user.id).order_by(Project.updated_at.desc()))
    projects = result.scalars().all()
    return [{"id": p.id, "title": p.title, "genre": p.genre, "theme": p.theme, "status": p.status,
             "target_chapters": p.target_chapters, "created_at": p.created_at, "updated_at": p.updated_at} for p in projects]


@router.post("/projects", status_code=201)
async def create_project(body: ProjectCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = Project(user_id=current_user.id, **body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return {"id": project.id, "title": project.title, "genre": project.genre, "status": project.status}


@router.get("/projects/{project_id}")
async def get_project(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ch_result = await db.execute(select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.position))
    chapters = ch_result.scalars().all()

    return {
        "id": project.id, "title": project.title, "genre": project.genre,
        "theme": project.theme, "status": project.status, "target_chapters": project.target_chapters,
        "chapters": [{"id": c.id, "title": c.title, "chapter_number": c.chapter_number,
                      "status": c.status, "word_count": c.word_count, "position": c.position,
                      "voice_match_score": c.voice_match_score} for c in chapters],
    }


@router.put("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(project, k, v)
    await db.commit()
    return {"updated": True}


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()


# ── Chapters ──────────────────────────────────

class ChapterCreate(BaseModel):
    title: str
    chapter_number: int
    intent: Optional[str] = None
    key_points: Optional[List[str]] = []
    anchor_scriptures: Optional[List[str]] = []
    testimony_ids: Optional[List[str]] = []


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    intent: Optional[str] = None
    key_points: Optional[List[str]] = None
    anchor_scriptures: Optional[List[str]] = None
    testimony_ids: Optional[List[str]] = None
    content: Optional[str] = None
    status: Optional[str] = None
    word_count: Optional[int] = None
    trigger_indexing: Optional[bool] = False


class ReorderRequest(BaseModel):
    order: List[str]  # list of chapter IDs in new order


@router.get("/projects/{project_id}/chapters")
async def list_chapters(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id, Chapter.user_id == current_user.id).order_by(Chapter.position)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/chapters", status_code=201)
async def create_chapter(project_id: str, body: ChapterCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Get max position
    result = await db.execute(select(Chapter).where(Chapter.project_id == project_id))
    existing = result.scalars().all()
    position = len(existing)

    chapter = Chapter(
        project_id=project_id,
        user_id=current_user.id,
        position=position,
        **body.model_dump()
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return {"id": chapter.id, "title": chapter.title, "chapter_number": chapter.chapter_number, "position": chapter.position}


@router.get("/projects/{project_id}/chapters/{chapter_id}")
async def get_chapter(project_id: str, chapter_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id, Chapter.user_id == current_user.id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@router.put("/projects/{project_id}/chapters/{chapter_id}")
async def update_chapter(project_id: str, chapter_id: str, body: ChapterUpdate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id, Chapter.user_id == current_user.id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    update_data = body.model_dump(exclude_none=True)
    update_data.pop("trigger_indexing", None)
    for k, v in update_data.items():
        setattr(chapter, k, v)

    await db.commit()

    # Schedule summary generation + companion-chat re-indexing if content
    # was updated AND trigger_indexing was explicitly requested.
    if body.content and body.trigger_indexing:
        from app.workers.tasks import generate_chapter_summary_task, index_chapter_task
        fire_background_job(background_tasks, generate_chapter_summary_task, chapter_id, job_name="generate_chapter_summary")
        fire_background_job(background_tasks, index_chapter_task, chapter_id, job_name="index_chapter")

    return {"updated": True}


@router.put("/projects/{project_id}/chapters/reorder")
async def reorder_chapters(project_id: str, body: ReorderRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    for i, chapter_id in enumerate(body.order):
        result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id))
        chapter = result.scalar_one_or_none()
        if chapter:
            chapter.position = i
    await db.commit()
    return {"reordered": True}


@router.delete("/projects/{project_id}/chapters/{chapter_id}", status_code=204)
async def delete_chapter(project_id: str, chapter_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id, Chapter.project_id == project_id, Chapter.user_id == current_user.id)
    )
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    await db.delete(chapter)
    await db.commit()


# ── Manuscript Companion Chat ──────────────────
# Whole-manuscript-aware assistant (distinct from the chapter-scoped
# /generate/chat). See app/services/ai/companion_chat.py.

class CompanionChatRequest(BaseModel):
    message: str


@router.get("/projects/{project_id}/companion-chat/history")
async def companion_chat_history(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    messages = await get_history(project_id, db)
    return [
        {
            "id": m.id, "role": m.role, "content": m.content,
            "referenced_chapter_ids": m.referenced_chapter_ids or [],
            "created_at": m.created_at,
        }
        for m in messages
    ]


@router.post("/projects/{project_id}/companion-chat")
async def companion_chat(
    project_id: str,
    body: CompanionChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    history_msgs = await get_history(project_id, db)
    history = [{"role": m.role, "content": m.content} for m in history_msgs]

    await save_message(project_id, current_user.id, "user", body.message, db)

    async def stream():
        buffer = []
        cited_ids: List[str] = []
        async for chunk in companion_chat_stream(project_id, body.message, history, db):
            if chunk.startswith("\n\n[CITED:"):
                cited_str = chunk.replace("\n\n[CITED:", "").rstrip("]")
                cited_ids[:] = [c for c in cited_str.split(",") if c]
            else:
                buffer.append(chunk)
                yield f"data: {json.dumps({'text': chunk})}\n\n"

        full_answer = "".join(buffer)
        if full_answer.strip():
            await save_message(project_id, current_user.id, "assistant", full_answer, db, referenced_chapter_ids=cited_ids)

        yield f"data: {json.dumps({'cited_chapter_ids': cited_ids})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
