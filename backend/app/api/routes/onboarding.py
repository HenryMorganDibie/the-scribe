"""
Onboarding routes — multi-step voice interview.
Includes: step save, live voice preview (SSE), finalization with background DNA extraction.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models import User, VoiceProfile
from app.core.security import get_current_user
from app.services.ai.generation import generate_voice_preview_stream
from app.utils.jobs import fire_background_job

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


ONBOARDING_STEPS = [
    "ministry_background",
    "theological_lens",
    "target_audience",
    "tone_preferences",
    "preferred_translation",
    "signature_phrases",
    "anchor_scriptures",
    "writing_samples",
    "personal_testimony",
]


class StepUpdate(BaseModel):
    step: int
    field: str
    value: object  # varies by step


class OnboardingComplete(BaseModel):
    data: dict  # full collected data


@router.get("/status")
async def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    return {
        "onboarded": current_user.onboarded,
        "current_step": profile.onboarding_step if profile else 0,
        "total_steps": len(ONBOARDING_STEPS),
    }


@router.put("/step")
async def save_step(
    body: StepUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    # Save raw step data to onboarding_data JSONB
    if not profile.onboarding_data:
        profile.onboarding_data = {}

    profile.onboarding_data[body.field] = body.value
    profile.onboarding_step = max(profile.onboarding_step, body.step + 1)

    # Also update the actual field if it maps directly
    field_map = {
        "ministry_background": "ministry_background",
        "theological_lens": "theological_lens",
        "target_audience": "target_audience",
        "tone_preferences": "tone_preferences",
        "preferred_translation": "preferred_translation",
        "writing_samples": "writing_samples",
    }
    if body.field in field_map:
        setattr(profile, field_map[body.field], body.value)

    await db.commit()
    return {"saved": True, "step": profile.onboarding_step}


@router.post("/preview")
async def voice_preview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Stream a live voice preview paragraph as the author fills in their profile.
    Called every 2-3 steps during onboarding — SSE stream.
    """
    result = await db.execute(
        select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    onboarding_data = profile.onboarding_data or {} if profile else {}

    async def event_stream():
        async for chunk in generate_voice_preview_stream(onboarding_data, profile):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/complete")
async def complete_onboarding(
    body: OnboardingComplete,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Finalize onboarding — update profile fields and kick off background DNA extraction.
    """
    result = await db.execute(
        select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    data = body.data

    # Persist all collected fields
    if "ministry_background" in data:
        profile.ministry_background = data["ministry_background"]
    if "theological_lens" in data:
        profile.theological_lens = data["theological_lens"]
    if "target_audience" in data:
        profile.target_audience = data["target_audience"]
    if "tone_preferences" in data:
        profile.tone_preferences = data["tone_preferences"]
    if "preferred_translation" in data:
        profile.preferred_translation = data["preferred_translation"]
    if "writing_samples" in data:
        profile.writing_samples = data["writing_samples"] if isinstance(data["writing_samples"], list) else [data["writing_samples"]]
    if "signature_phrases" in data:
        profile.signature_phrases = data["signature_phrases"] if isinstance(data["signature_phrases"], list) else []

    profile.onboarding_data = data
    profile.onboarding_step = len(ONBOARDING_STEPS)
    current_user.onboarded = True

    await db.commit()

    # Schedule background work — non-blocking; runs after this response is
    # sent (see app.utils.jobs / app.workers.tasks).
    from app.workers.tasks import extract_voice_dna_task, index_writing_samples_task

    fire_background_job(background_tasks, extract_voice_dna_task, current_user.id, job_name="extract_voice_dna")
    if profile.writing_samples:
        fire_background_job(background_tasks, index_writing_samples_task, current_user.id, job_name="index_writing_samples")

    return {"onboarded": True, "message": "Voice profile is being processed in the background."}
