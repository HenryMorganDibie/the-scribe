import json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from pydantic import BaseModel, Field
from typing import Literal, Optional, List

from app.db.session import get_db
from app.models import User, Project, Chapter, ChapterVersion, DocumentEmbedding, Sermon, VoiceProfile
from app.core.config import settings
from app.core.security import get_current_user
from app.api.ownership import get_owned_chapter, get_owned_project
from app.utils.jobs import fire_background_job
from app.services.ai.companion_chat import companion_chat_stream, save_message, get_history
from app.services.ai.sermon_book import build_sermon_book_plan
from app.services.packs import pack_for
from app.services.chapter_versions import AUTOSAVE_INTERVAL, snapshot_chapter
from app.services.progress import record_words
from app.services.security.rate_limits import consume_user_quota

router = APIRouter(tags=["projects"])


# ── Projects ──────────────────────────────────

class ProjectCreate(BaseModel):
    title: str
    genre: Optional[str] = "teaching"
    theme: Optional[str] = None
    target_chapters: Optional[int] = 10


class ProjectUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    genre: Optional[str] = Field(default=None, max_length=80)
    theme: Optional[str] = Field(default=None, max_length=2_000)
    target_chapters: Optional[int] = Field(default=None, ge=1, le=100)
    status: Optional[str] = Field(default=None, max_length=20)
    # Per-book style — empty string / empty list clears the override.
    target_audience: Optional[str] = Field(default=None, max_length=2_000)
    style_rules: Optional[List[str]] = Field(default=None, max_length=30)
    style_notes: Optional[str] = Field(default=None, max_length=5_000)
    # Linked source library (ids of the author's processed sources).
    source_sermon_ids: Optional[List[str]] = Field(default=None, max_length=50)
    # Goals. 0 clears a numeric goal; clear_deadline removes the deadline.
    target_word_count: Optional[int] = Field(default=None, ge=0, le=2_000_000)
    daily_word_goal: Optional[int] = Field(default=None, ge=0, le=100_000)
    deadline: Optional[date] = None
    clear_deadline: bool = False


class SermonBookCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    target_reader: str = Field(default="", max_length=1000)
    sermon_ids: List[str] = Field(min_length=1, max_length=10)
    target_chapters: int = Field(default=8, ge=3, le=20)


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


@router.post("/projects/from-sermons", status_code=201)
async def create_project_from_sermons(
    body: SermonBookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a chapter-by-chapter book blueprint grounded in selected sermons."""
    requested_ids = list(dict.fromkeys(body.sermon_ids))
    result = await db.execute(
        select(Sermon).where(
            Sermon.id.in_(requested_ids),
            Sermon.user_id == current_user.id,
            Sermon.status == "complete",
        )
    )
    sermons = result.scalars().all()
    if len(sermons) != len(requested_ids):
        raise HTTPException(status_code=400, detail="Select only completed sermons from your library")

    profile_result = await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == current_user.id))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=400, detail="Complete your voice profile before building a book")
    await consume_user_quota(db, current_user.id, "ai_request", settings.AI_DAILY_REQUEST_LIMIT)

    try:
        plan = await build_sermon_book_plan(
            title=body.title,
            target_reader=body.target_reader,
            target_chapters=body.target_chapters,
            theological_lens=profile.theological_lens,
            preferred_translation=profile.preferred_translation,
            guardrails=profile.theological_guardrails,
            sermons=sermons,
            pack=pack_for(profile),
        )
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    project = Project(
        user_id=current_user.id,
        title=body.title,
        genre="teaching" if pack_for(profile).uses_scripture else profile.theological_lens,
        theme=plan["theme"] or f"A book for {body.target_reader}".strip(),
        target_chapters=len(plan["chapters"]),
        source_sermon_ids=requested_ids,
    )
    db.add(project)
    await db.flush()
    for position, chapter_data in enumerate(plan["chapters"]):
        db.add(Chapter(
            project_id=project.id,
            user_id=current_user.id,
            position=position,
            chapter_number=position + 1,
            **chapter_data,
        ))
    await db.commit()
    await db.refresh(project)
    return {
        "id": project.id,
        "title": project.title,
        "theme": project.theme,
        "chapter_count": len(plan["chapters"]),
        "source_sermons": [{"id": sermon.id, "title": sermon.title} for sermon in sermons],
    }


@router.get("/projects/{project_id}")
async def get_project(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await get_owned_project(project_id, current_user.id, db)

    ch_result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.user_id == current_user.id,
        ).order_by(Chapter.position)
    )
    chapters = ch_result.scalars().all()
    source_sermons = []
    if project.source_sermon_ids:
        sermon_result = await db.execute(
            select(Sermon).where(
                Sermon.id.in_(project.source_sermon_ids),
                Sermon.user_id == current_user.id,
            )
        )
        source_sermons = [{"id": sermon.id, "title": sermon.title} for sermon in sermon_result.scalars().all()]

    return {
        "id": project.id, "title": project.title, "genre": project.genre,
        "theme": project.theme, "status": project.status, "target_chapters": project.target_chapters,
        "target_audience": project.target_audience, "style_rules": project.style_rules or [],
        "style_notes": project.style_notes,
        "target_word_count": project.target_word_count, "daily_word_goal": project.daily_word_goal,
        "deadline": project.deadline,
        "source_sermons": source_sermons,
        "chapters": [{"id": c.id, "title": c.title, "chapter_number": c.chapter_number,
                      "status": c.status, "word_count": c.word_count, "position": c.position,
                      "voice_match_score": c.voice_match_score} for c in chapters],
    }


@router.put("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await get_owned_project(project_id, current_user.id, db)
    updates = body.model_dump(exclude_none=True)

    if updates.pop("clear_deadline", False):
        updates["deadline"] = None
    for goal in ("target_word_count", "daily_word_goal"):
        if updates.get(goal) == 0:
            updates[goal] = None
    if "style_rules" in updates:
        updates["style_rules"] = [r.strip()[:300] for r in updates["style_rules"] if r.strip()]
    for field in ("target_audience", "style_notes"):
        if field in updates:
            updates[field] = updates[field].strip() or None
    if "source_sermon_ids" in updates:
        requested = list(dict.fromkeys(updates["source_sermon_ids"]))
        if requested:
            owned = (await db.execute(
                select(Sermon.id).where(Sermon.id.in_(requested), Sermon.user_id == current_user.id)
            )).scalars().all()
            if len(owned) != len(requested):
                raise HTTPException(status_code=400, detail="Link only sources from your own library")
        updates["source_sermon_ids"] = requested

    for k, v in updates.items():
        setattr(project, k, v)
    await db.commit()
    return {"updated": True}


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    project = await get_owned_project(project_id, current_user.id, db)
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


class SceneItem(BaseModel):
    """One planned scene (fiction) or section (non-fiction) of a chapter."""
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=2_000)
    pov: str = Field(default="", max_length=120)
    setting: str = Field(default="", max_length=200)


class ChapterUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    intent: Optional[str] = Field(default=None, max_length=4_000)
    key_points: Optional[List[str]] = Field(default=None, max_length=30)
    # Ordered scene/section plan; [] clears it.
    scenes: Optional[List[SceneItem]] = Field(default=None, max_length=40)
    anchor_scriptures: Optional[List[str]] = None
    testimony_ids: Optional[List[str]] = None
    content: Optional[str] = None
    # Stage: draft (Outline) | in_progress (Drafted) | revised | complete (Done)
    status: Optional[Literal["draft", "in_progress", "revised", "complete"]] = None
    word_count: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    trigger_indexing: Optional[bool] = False


class ReorderRequest(BaseModel):
    order: List[str]  # list of chapter IDs in new order


@router.get("/projects/{project_id}/chapters")
async def list_chapters(project_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_owned_project(project_id, current_user.id, db)
    result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id, Chapter.user_id == current_user.id).order_by(Chapter.position)
    )
    return result.scalars().all()


@router.post("/projects/{project_id}/chapters", status_code=201)
async def create_chapter(project_id: str, body: ChapterCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_owned_project(project_id, current_user.id, db)

    # Get max position
    result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.user_id == current_user.id,
        )
    )
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
    await get_owned_project(project_id, current_user.id, db)
    return await get_owned_chapter(
        chapter_id,
        current_user.id,
        db,
        project_id=project_id,
    )


# NOTE: This route MUST be defined before PUT /{chapter_id} so FastAPI does not
# match the literal string "reorder" as a chapter_id path parameter.
@router.put("/projects/{project_id}/chapters/reorder")
async def reorder_chapters(project_id: str, body: ReorderRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_owned_project(project_id, current_user.id, db)
    result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.user_id == current_user.id,
        )
    )
    chapters = result.scalars().all()
    chapters_by_id = {chapter.id: chapter for chapter in chapters}

    # Require one occurrence of every chapter in this project. Besides keeping
    # positions coherent, this prevents foreign chapter IDs from being used as
    # a cross-tenant write primitive.
    if len(body.order) != len(set(body.order)) or set(body.order) != set(chapters_by_id):
        raise HTTPException(
            status_code=400,
            detail="Order must contain every project chapter exactly once",
        )

    for position, chapter_id in enumerate(body.order):
        chapters_by_id[chapter_id].position = position
    await db.commit()
    return {"reordered": True}


@router.put("/projects/{project_id}/chapters/{chapter_id}")
async def update_chapter(project_id: str, chapter_id: str, body: ChapterUpdate, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_owned_project(project_id, current_user.id, db)
    chapter = await get_owned_chapter(
        chapter_id,
        current_user.id,
        db,
        project_id=project_id,
    )

    # Keep the outgoing draft in history before it's overwritten. Autosaves
    # are throttled; explicit saves (trigger_indexing) always keep a copy.
    if body.content is not None and body.content != chapter.content:
        if body.trigger_indexing:
            await snapshot_chapter(db, chapter, "manual")
        else:
            await snapshot_chapter(db, chapter, "autosave", min_interval=AUTOSAVE_INTERVAL)

    # Log how much the manuscript grew or shrank today (goals, pace, streaks).
    if body.word_count is not None:
        await record_words(db, project_id, current_user.id, body.word_count - (chapter.word_count or 0))

    update_data = body.model_dump(exclude_none=True)
    update_data.pop("trigger_indexing", None)
    for k, v in update_data.items():
        setattr(chapter, k, v)

    await db.commit()

    # Schedule summary generation + companion-chat re-indexing if content
    # was updated AND trigger_indexing was explicitly requested.
    if body.content and body.trigger_indexing:
        _schedule_chapter_indexing(background_tasks, chapter_id)

    return {"updated": True}


def _schedule_chapter_indexing(background_tasks: BackgroundTasks, chapter_id: str) -> None:
    from app.workers.tasks import generate_chapter_summary_task, index_chapter_task
    fire_background_job(background_tasks, generate_chapter_summary_task, chapter_id, job_name="generate_chapter_summary")
    fire_background_job(background_tasks, index_chapter_task, chapter_id, job_name="index_chapter")


# ── Chapter draft history ─────────────────────

def _serialize_version(v: ChapterVersion, *, with_content: bool = False) -> dict:
    data = {"id": v.id, "reason": v.reason, "word_count": v.word_count, "created_at": v.created_at}
    if with_content:
        data["content"] = v.content
    return data


async def _get_owned_version(version_id: str, chapter: Chapter, db: AsyncSession) -> ChapterVersion:
    version = (await db.execute(
        select(ChapterVersion).where(
            ChapterVersion.id == version_id,
            ChapterVersion.chapter_id == chapter.id,
            ChapterVersion.user_id == chapter.user_id,
        )
    )).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.get("/projects/{project_id}/chapters/{chapter_id}/versions")
async def list_chapter_versions(project_id: str, chapter_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chapter = await get_owned_chapter(chapter_id, current_user.id, db, project_id=project_id)
    result = await db.execute(
        select(ChapterVersion)
        .where(ChapterVersion.chapter_id == chapter.id, ChapterVersion.user_id == current_user.id)
        .order_by(ChapterVersion.created_at.desc())
    )
    return [_serialize_version(v) for v in result.scalars().all()]


@router.get("/projects/{project_id}/chapters/{chapter_id}/versions/{version_id}")
async def get_chapter_version(project_id: str, chapter_id: str, version_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chapter = await get_owned_chapter(chapter_id, current_user.id, db, project_id=project_id)
    return _serialize_version(await _get_owned_version(version_id, chapter, db), with_content=True)


@router.post("/projects/{project_id}/chapters/{chapter_id}/versions/{version_id}/restore")
async def restore_chapter_version(project_id: str, chapter_id: str, version_id: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    chapter = await get_owned_chapter(chapter_id, current_user.id, db, project_id=project_id)
    version = await _get_owned_version(version_id, chapter, db)

    # The current draft becomes a version too, so the restore can be undone.
    await snapshot_chapter(db, chapter, "before_restore")
    chapter.content = version.content
    chapter.word_count = version.word_count or 0
    await db.commit()

    _schedule_chapter_indexing(background_tasks, chapter.id)
    return {"content": chapter.content, "word_count": chapter.word_count}


@router.delete("/projects/{project_id}/chapters/{chapter_id}", status_code=204)
async def delete_chapter(project_id: str, chapter_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await get_owned_project(project_id, current_user.id, db)
    chapter = await get_owned_chapter(
        chapter_id,
        current_user.id,
        db,
        project_id=project_id,
    )
    # Chapter chunks reference the chapter only by source_id (no FK), so
    # remove them explicitly or Companion Chat keeps citing a deleted chapter.
    await db.execute(
        delete(DocumentEmbedding).where(
            DocumentEmbedding.doc_type == "chapter",
            DocumentEmbedding.source_id == chapter_id,
        )
    )
    await db.delete(chapter)
    await db.commit()


# ── Manuscript Companion Chat ──────────────────
# Whole-manuscript-aware assistant (distinct from the chapter-scoped
# /generate/chat). See app/services/ai/companion_chat.py.

class CompanionChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5_000)


@router.get("/projects/{project_id}/companion-chat/history")
async def companion_chat_history(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_project(project_id, current_user.id, db)

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
    await get_owned_project(project_id, current_user.id, db)
    await consume_user_quota(db, current_user.id, "ai_request", settings.AI_DAILY_REQUEST_LIMIT)

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
