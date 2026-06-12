from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import User, Project, Chapter
from app.core.security import get_current_user
from app.services.export.docx_export import create_manuscript_docx

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/project/{project_id}")
async def export_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    ch_result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.position)
    )
    chapters = ch_result.scalars().all()

    docx_bytes = create_manuscript_docx(
        title=project.title,
        author_name=current_user.full_name or current_user.email,
        chapters=[{"number": c.chapter_number, "title": c.title, "content": c.content or ""} for c in chapters],
    )

    filename = f"{project.title.lower().replace(' ', '-')}-manuscript.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/chapter/{chapter_id}")
async def export_chapter(
    chapter_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id, Chapter.user_id == current_user.id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    project_result = await db.execute(select(Project).where(Project.id == chapter.project_id))
    project = project_result.scalar_one_or_none()

    docx_bytes = create_manuscript_docx(
        title=project.title if project else "Manuscript",
        author_name=current_user.full_name or current_user.email,
        chapters=[{"number": chapter.chapter_number, "title": chapter.title, "content": chapter.content or ""}],
    )

    filename = f"chapter-{chapter.chapter_number}-{chapter.title.lower().replace(' ', '-')}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
