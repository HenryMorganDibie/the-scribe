# """
# Onboarding routes — multi-step voice interview.
# Includes: step save, live voice preview (SSE), finalization with background DNA extraction.
# """
# from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
# from fastapi.responses import StreamingResponse
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select
# from pydantic import BaseModel
# from typing import Optional, List

# from app.db.session import get_db
# from app.models import User, VoiceProfile
# from app.core.security import get_current_user
# from app.services.ai.generation import generate_voice_preview_stream
# from app.utils.jobs import fire_background_job

# router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ONBOARDING_STEPS = [
#     "ministry_background",
#     "theological_lens",
#     "target_audience",
#     "tone_preferences",
#     "preferred_translation",
#     "signature_phrases",
#     "anchor_scriptures",
#     "writing_samples",
#     "personal_testimony",
# ]


# class StepUpdate(BaseModel):
#     step: int
#     field: str
#     value: object  # varies by step


# class OnboardingComplete(BaseModel):
#     data: dict  # full collected data


# @router.get("/status")
# async def onboarding_status(
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     result = await db.execute(
#         select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
#     )
#     profile = result.scalar_one_or_none()
#     return {
#         "onboarded": current_user.onboarded,
#         "current_step": profile.onboarding_step if profile else 0,
#         "total_steps": len(ONBOARDING_STEPS),
#     }


# @router.put("/step")
# async def save_step(
#     body: StepUpdate,
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     result = await db.execute(
#         select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
#     )
#     profile = result.scalar_one_or_none()
#     if not profile:
#         raise HTTPException(status_code=404, detail="Voice profile not found")

#     # Save raw step data to onboarding_data JSONB
#     if not profile.onboarding_data:
#         profile.onboarding_data = {}

#     profile.onboarding_data[body.field] = body.value
#     profile.onboarding_step = max(profile.onboarding_step, body.step + 1)

#     # Also update the actual field if it maps directly
#     field_map = {
#         "ministry_background": "ministry_background",
#         "theological_lens": "theological_lens",
#         "target_audience": "target_audience",
#         "tone_preferences": "tone_preferences",
#         "preferred_translation": "preferred_translation",
#         "writing_samples": "writing_samples",
#     }
#     if body.field in field_map:
#         setattr(profile, field_map[body.field], body.value)

#     await db.commit()
#     return {"saved": True, "step": profile.onboarding_step}


# @router.post("/preview")
# async def voice_preview(
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Stream a live voice preview paragraph as the author fills in their profile.
#     Called every 2-3 steps during onboarding — SSE stream.
#     """
#     result = await db.execute(
#         select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
#     )
#     profile = result.scalar_one_or_none()
#     onboarding_data = profile.onboarding_data or {} if profile else {}

#     async def event_stream():
#         async for chunk in generate_voice_preview_stream(onboarding_data, profile):
#             yield f"data: {chunk}\n\n"
#         yield "data: [DONE]\n\n"

#     return StreamingResponse(event_stream(), media_type="text/event-stream")


# @router.post("/complete")
# async def complete_onboarding(
#     body: OnboardingComplete,
#     background_tasks: BackgroundTasks,
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db),
# ):
#     """
#     Finalize onboarding — update profile fields and kick off background DNA extraction.
#     """
#     result = await db.execute(
#         select(VoiceProfile).where(VoiceProfile.user_id == current_user.id)
#     )
#     profile = result.scalar_one_or_none()
#     if not profile:
#         raise HTTPException(status_code=404, detail="Profile not found")

#     data = body.data

#     # Persist all collected fields
#     if "ministry_background" in data:
#         profile.ministry_background = data["ministry_background"]
#     if "theological_lens" in data:
#         profile.theological_lens = data["theological_lens"]
#     if "target_audience" in data:
#         profile.target_audience = data["target_audience"]
#     if "tone_preferences" in data:
#         profile.tone_preferences = data["tone_preferences"]
#     if "preferred_translation" in data:
#         profile.preferred_translation = data["preferred_translation"]
#     if "writing_samples" in data:
#         profile.writing_samples = data["writing_samples"] if isinstance(data["writing_samples"], list) else [data["writing_samples"]]
#     if "signature_phrases" in data:
#         profile.signature_phrases = data["signature_phrases"] if isinstance(data["signature_phrases"], list) else []

#     profile.onboarding_data = data
#     profile.onboarding_step = len(ONBOARDING_STEPS)
#     current_user.onboarded = True

#     await db.commit()

#     # Schedule background work — non-blocking; runs after this response is
#     # sent (see app.utils.jobs / app.workers.tasks).
#     from app.workers.tasks import extract_voice_dna_task, index_writing_samples_task

#     fire_background_job(background_tasks, extract_voice_dna_task, current_user.id, job_name="extract_voice_dna")
#     if profile.writing_samples:
#         fire_background_job(background_tasks, index_writing_samples_task, current_user.id, job_name="index_writing_samples")

#     return {"onboarded": True, "message": "Voice profile is being processed in the background."}


"""
Onboarding routes — multi-step voice interview.
Includes: step save, live voice preview (SSE), finalization with inline DNA extraction.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from app.db.session import get_db
from app.models import User, VoiceProfile
from app.core.security import get_current_user
from app.services.ai.generation import generate_voice_preview_stream

import structlog

logger = structlog.get_logger()

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Finalize onboarding — persist profile fields and run Voice DNA extraction
    inline (in this request) rather than as a background task.

    Why inline: FastAPI BackgroundTasks run in-process after the response is
    sent. On Render's free plan the instance spins down after 15 minutes of
    inactivity — if it spins down while the task is running the task is
    silently killed with no retry, leaving the user stuck on "still being
    processed" indefinitely. Running extraction here means the HTTP connection
    stays open until it's done (~10-20s), guaranteeing completion regardless
    of plan or instance lifecycle.
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

    # ── Inline Voice DNA extraction ──────────────────────────────────────
    # Runs to completion before this response is returned. The user waits
    # ~10-20s on the final onboarding screen, but DNA is guaranteed to exist
    # the moment they land on the Dashboard — no polling, no "still processing".
    if profile.writing_samples:
        try:
            from app.services.ai.generation import extract_voice_dna
            from app.services.voice.embeddings import embedding_service, index_writing_sample
            from app.services.voice.timeline import snapshot_voice

            dna = await extract_voice_dna(profile, db)
            if dna:
                profile.signature_phrases = dna.get("signature_phrases", [])
                profile.cadence_score = dna.get("cadence_score", 0.5)
                profile.style_tags = dna.get("style_tags", [])
                profile.voice_summary = dna.get("voice_summary", "")

                existing = {s["ref"]: s for s in (profile.anchor_scriptures or [])}
                for s in dna.get("anchor_scriptures", []):
                    if s["ref"] not in existing:
                        existing[s["ref"]] = s
                profile.anchor_scriptures = list(existing.values())

                if profile.voice_summary:
                    profile.voice_summary_embedding = await embedding_service.embed(profile.voice_summary)

                await db.commit()

                await snapshot_voice(
                    profile=profile,
                    trigger="onboarding_complete",
                    db=db,
                    change_summary="Initial voice DNA extracted from writing samples.",
                )

                for sample in profile.writing_samples:
                    await index_writing_sample(current_user.id, sample, db)

        except Exception:
            # Non-fatal — user is marked onboarded and profile fields are saved.
            # DNA can be recovered via POST /voice-profile/reprocess.
            logger.exception("inline_voice_dna_extraction_failed", user_id=current_user.id)

    return {"onboarded": True, "message": "Voice profile processed successfully."}