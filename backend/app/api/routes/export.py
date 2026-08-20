from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import User, Chapter
from app.core.security import get_current_user
from app.api.ownership import get_owned_chapter, get_owned_project
from app.services.export.docx_export import create_manuscript_docx

router = APIRouter(prefix="/export", tags=["export"])


@router.post("/project/{project_id}")
async def export_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_owned_project(project_id, current_user.id, db)

    ch_result = await db.execute(
        select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.user_id == current_user.id,
        ).order_by(Chapter.position)
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
    chapter = await get_owned_chapter(chapter_id, current_user.id, db)
    project = await get_owned_project(chapter.project_id, current_user.id, db)

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
