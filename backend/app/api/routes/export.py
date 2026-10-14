import re
import unicodedata
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models import User, Chapter
from app.core.security import get_current_user
from app.api.ownership import get_owned_chapter, get_owned_project
from app.services.export.docx_export import create_manuscript_docx
from app.services.export.pdf_export import create_manuscript_pdf

router = APIRouter(prefix="/export", tags=["export"])

_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def _content_disposition(filename: str) -> str:
    """Build an attachment header that survives any title.

    Starlette encodes headers as Latin-1, so smart quotes, em dashes and
    non-Latin titles raise on a raw filename. Send an ASCII fallback plus the
    RFC 5987 UTF-8 form, which browsers prefer when present.
    """
    filename = re.sub(r'[\x00-\x1f\x7f"\\/]', "", filename)
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_name).strip("-.") or "manuscript"
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"


def _render_manuscript(fmt: str, title: str, author_name: str, chapters: list[dict]) -> bytes:
    if fmt == "pdf":
        return create_manuscript_pdf(title=title, author_name=author_name, chapters=chapters)
    return create_manuscript_docx(title=title, author_name=author_name, chapters=chapters)


@router.post("/project/{project_id}")
async def export_project(
    project_id: str,
    format: Literal["docx", "pdf"] = "docx",
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

    manuscript_bytes = _render_manuscript(
        format,
        title=project.title,
        author_name=current_user.full_name or current_user.email,
        chapters=[{"number": c.chapter_number, "title": c.title, "content": c.content or ""} for c in chapters],
    )

    filename = f"{project.title.lower().replace(' ', '-')}-manuscript.{format}"
    return Response(
        content=manuscript_bytes,
        media_type=_MEDIA_TYPES[format],
        headers={"Content-Disposition": _content_disposition(filename)},
    )


@router.post("/chapter/{chapter_id}")
async def export_chapter(
    chapter_id: str,
    format: Literal["docx", "pdf"] = "docx",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await get_owned_chapter(chapter_id, current_user.id, db)
    project = await get_owned_project(chapter.project_id, current_user.id, db)

    manuscript_bytes = _render_manuscript(
        format,
        title=project.title if project else "Manuscript",
        author_name=current_user.full_name or current_user.email,
        chapters=[{"number": chapter.chapter_number, "title": chapter.title, "content": chapter.content or ""}],
    )

    filename = f"chapter-{chapter.chapter_number}-{chapter.title.lower().replace(' ', '-')}.{format}"
    return Response(
        content=manuscript_bytes,
        media_type=_MEDIA_TYPES[format],
        headers={"Content-Disposition": _content_disposition(filename)},
    )
