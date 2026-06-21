"""Sermon upload & ingestion routes. Upload accepts a file OR pasted text (multipart)."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db.session import get_db
from app.models import User, Sermon, DocumentEmbedding
from app.core.security import get_current_user
from app.services.ingestion.pipeline import process_sermon

router = APIRouter(prefix="/sermons", tags=["sermons"])

_EXT_TO_TYPE = {"pdf": "pdf", "docx": "docx"}


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
    title: str = Form(...),
    text: Optional[str] = Form(None),
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
        file_bytes = await file.read()
    else:
        source_type = "text"

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
