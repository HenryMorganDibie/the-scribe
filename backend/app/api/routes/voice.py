from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models import User, VoiceProfile, Testimony
from app.core.security import get_current_user
from app.services.voice.timeline import get_timeline, snapshot_voice, diff_versions
from app.utils.jobs import fire_background_job

router = APIRouter(tags=["voice"])


# ── Voice Profile ──────────────────────────────

class VoiceProfileUpdate(BaseModel):
    theological_lens: Optional[str] = None
    tone_preferences: Optional[List[str]] = None
    preferred_translation: Optional[str] = None
    signature_phrases: Optional[List[str]] = None
    anchor_scriptures: Optional[list] = None
    cadence_score: Optional[float] = None
    style_tags: Optional[List[str]] = None
    voice_summary: Optional[str] = None


@router.get("/voice-profile")
async def get_voice_profile(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return profile


@router.put("/voice-profile")
async def update_voice_profile(
    body: VoiceProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == current_user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    for k, v in body.model_dump(exclude_none=True).items():
        setattr(profile, k, v)

    await db.commit()

    # Snapshot voice version on manual edit
    await snapshot_voice(profile=profile, trigger="manual_update", db=db, change_summary="User manually updated voice profile.")

    return {"updated": True}


@router.get("/voice/dna-report")
async def dna_report(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import Sermon
    from app.services.ai.dna_report import compute_dna_metrics, generate_dna_narrative

    profile = (await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == current_user.id))).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    sermons = (await db.execute(
        select(Sermon).where(Sermon.user_id == current_user.id, Sermon.status == "complete")
    )).scalars().all()
    versions = await get_timeline(current_user.id, db)

    metrics = compute_dna_metrics(profile, sermons, versions)

    if not profile.dna_narrative:
        narrative = await generate_dna_narrative(metrics)
        profile.dna_narrative = narrative
        await db.commit()
    else:
        narrative = profile.dna_narrative

    return {"metrics": metrics, "narrative": narrative, "sermon_count": len(sermons)}


# ── Voice Evolution Timeline ──────────────────

@router.get("/voice-profile/timeline")
async def voice_timeline(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    versions = await get_timeline(current_user.id, db)
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "trigger": v.trigger,
            "change_summary": v.change_summary,
            "cadence_score": v.cadence_score,
            "phrase_count": v.phrase_count,
            "scripture_count": v.scripture_count,
            "created_at": v.created_at,
        }
        for v in versions
    ]


@router.get("/voice-profile/timeline/diff")
async def voice_diff(v1: int, v2: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import VoiceVersion
    versions = await get_timeline(current_user.id, db)
    ver_map = {v.version_number: v for v in versions}

    if v1 not in ver_map or v2 not in ver_map:
        raise HTTPException(status_code=404, detail="Version not found")

    return await diff_versions(ver_map[v1], ver_map[v2])


# ── Testimony Vault ────────────────────────────

class TestimonyCreate(BaseModel):
    title: str
    story: str
    themes: Optional[List[str]] = []


class TestimonyUpdate(BaseModel):
    title: Optional[str] = None
    story: Optional[str] = None
    themes: Optional[List[str]] = None


@router.get("/testimonies")
async def list_testimonies(
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Testimony).where(Testimony.user_id == current_user.id)
    if status:
        query = query.where(Testimony.status == status)
    query = query.order_by(Testimony.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/testimonies", status_code=201)
async def create_testimony(body: TestimonyCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t = Testimony(user_id=current_user.id, **body.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)

    # Index for vector retrieval — non-blocking, see app.utils.jobs
    from app.workers.tasks import index_testimony_task
    fire_background_job(index_testimony_task, current_user.id, t.id, t.story, job_name="index_testimony")

    return {"id": t.id, "title": t.title}


@router.post("/testimonies/{testimony_id}/approve")
async def approve_testimony(testimony_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Testimony).where(Testimony.id == testimony_id, Testimony.user_id == current_user.id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Testimony not found")
    t.status = "approved"
    await db.commit()
    # Index for retrieval now that it's part of the vault
    from app.workers.tasks import index_testimony_task
    fire_background_job(index_testimony_task, current_user.id, t.id, t.story, job_name="index_testimony")
    return {"approved": True, "id": t.id}


@router.put("/testimonies/{testimony_id}")
async def update_testimony(testimony_id: str, body: TestimonyUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Testimony).where(Testimony.id == testimony_id, Testimony.user_id == current_user.id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Testimony not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(t, k, v)
    await db.commit()
    return {"updated": True}


@router.delete("/testimonies/{testimony_id}", status_code=204)
async def delete_testimony(testimony_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Testimony).where(Testimony.id == testimony_id, Testimony.user_id == current_user.id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Testimony not found")
    await db.delete(t)
    await db.commit()
