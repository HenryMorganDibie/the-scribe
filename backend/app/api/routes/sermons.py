"""Sermon upload & ingestion routes. Upload accepts a file OR pasted text (multipart)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db.session import get_db
from app.models import User, Sermon, DocumentEmbedding
from app.core.security import get_current_user
from app.core.config import settings
from app.services.ingestion.pipeline import process_sermon
from app.services.security.rate_limits import consume_user_quota

router = APIRouter(prefix="/sermons", tags=["sermons"])

_EXT_TO_TYPE = {"pdf": "pdf", "docx": "docx"}


async def _read_upload_limited(file: UploadFile, limit: int) -> bytes:
    """Read an upload in chunks and stop before it can exhaust API memory."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=413, detail=f"File is too large. Limit is {limit // (1024 * 1024)} MB.")
        chunks.append(chunk)
    return b"".join(chunks)


def _serialize(s: Sermon) -> dict:
    return {
        "id": s.id, "title": s.title, "source_type": s.source_type, "status": s.status,
        "word_count": s.word_count, "phrases_added": s.phrases_added,
        "testimonies_suggested": s.testimonies_suggested, "error_message": s.error_message,
        "created_at": s.created_at, "processed_at": s.processed_at,
    }


@router.post("", status_code=202)
async def upload_sermon(
    background_tasks: BackgroundTasks,
    title: str = Form(..., max_length=160),
    text: Optional[str] = Form(None, max_length=settings.MAX_PASTED_TEXT_CHARS),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not text and not file:
        raise HTTPException(status_code=400, detail="Provide either pasted text or a file.")

    file_bytes = None
    filename = None
    if file:
        filename = file.filename or ""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in _EXT_TO_TYPE:
            source_type = _EXT_TO_TYPE[ext]
        elif ext in ("mp3", "m4a", "wav", "mpga"):
            source_type = "audio"
        elif ext in ("mp4", "webm", "mov", "mkv"):
            # Video containers are NOT supported yet -- this pipeline has no
            # video/audio-track extraction step. Sending a raw video file to
            # Groq's audio transcription endpoint silently misbehaves (huge
            # upload for the file size limit, undefined transcription
            # behavior) rather than failing clearly, which is exactly what
            # was happening here before this fix. Reject explicitly instead.
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Video files (.{ext}) aren't supported yet -- only the audio track can be "
                    "transcribed, and that extraction step doesn't exist yet. "
                    "Please upload an audio file (.mp3, .m4a, .wav) instead, or extract the audio "
                    "from your video first."
                ),
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")
        file_bytes = await _read_upload_limited(file, settings.MAX_UPLOAD_BYTES)
        if source_type == "pdf" and not file_bytes.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")
        if source_type == "docx" and not file_bytes.startswith(b"PK"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid DOCX file.")
    else:
        source_type = "text"

    await consume_user_quota(db, current_user.id, "sermon_upload", settings.SERMON_DAILY_UPLOAD_LIMIT)

    sermon = Sermon(
        user_id=current_user.id, title=title, source_type=source_type,
        original_filename=filename, status="pending",
    )
    db.add(sermon)
    await db.commit()
    await db.refresh(sermon)

    background_tasks.add_task(
        process_sermon, sermon.id, source_type,
        file_bytes=file_bytes, text_value=text, filename=filename,
    )
    return {"id": sermon.id, "status": sermon.status}


@router.get("")
async def list_sermons(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sermon).where(Sermon.user_id == current_user.id).order_by(Sermon.created_at.desc())
    )
    return [_serialize(s) for s in result.scalars().all()]


@router.get("/{sermon_id}")
async def get_sermon(sermon_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sermon).where(Sermon.id == sermon_id, Sermon.user_id == current_user.id)
    )
    sermon = result.scalar_one_or_none()
    if not sermon:
        raise HTTPException(status_code=404, detail="Sermon not found")
    return _serialize(sermon)


@router.delete("/{sermon_id}", status_code=204)
async def delete_sermon(sermon_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Sermon).where(Sermon.id == sermon_id, Sermon.user_id == current_user.id)
    )
    sermon = result.scalar_one_or_none()
    if not sermon:
        raise HTTPException(status_code=404, detail="Sermon not found")
    # Remove this sermon's embeddings too
    await db.execute(
        DocumentEmbedding.__table__.delete().where(
            (DocumentEmbedding.doc_type == "sermon") & (DocumentEmbedding.source_id == sermon_id)
        )
    )
    await db.delete(sermon)
    await db.commit()
