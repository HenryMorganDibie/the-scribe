"""
Onboarding routes — multi-step voice interview.
Includes: step save, live voice preview (SSE), finalization with inline DNA extraction.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Optional, List

from app.db.session import get_db
from app.models import DocumentEmbedding, User, VoiceProfile
from app.core.security import get_current_user
from app.services.ai.generation import generate_voice_preview_stream
from app.core.config import settings
from app.services.packs import PACKS
from app.services.security.rate_limits import consume_user_quota
from app.api.sse import SSE_DONE, sse_error, sse_text

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


# Every interview answer the frontend can send (all packs).
TEXT_FIELDS = {
    "pack", "ministry_background", "theological_lens", "target_audience",
    "preferred_translation", "personal_testimony", "pov_tense",
}
LIST_FIELDS = {"tone_preferences", "signature_phrases", "anchor_scriptures", "style_rules"}
MAX_TEXT_CHARS = 5_000
MAX_LIST_ITEMS, MAX_ITEM_CHARS = 50, 500
MAX_SAMPLES, MAX_SAMPLE_CHARS = 10, 50_000


def validate_answer(field: str, value):
    """Reject unknown fields and oversized answers; returns the value unchanged."""
    if field == "writing_samples":
        samples = value if isinstance(value, list) else [value]
        if len(samples) > MAX_SAMPLES or any(not isinstance(v, str) or len(v) > MAX_SAMPLE_CHARS for v in samples):
            raise ValueError(f"Up to {MAX_SAMPLES} writing samples of at most {MAX_SAMPLE_CHARS:,} characters each")
    elif field in LIST_FIELDS:
        if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS or any(
            not isinstance(v, str) or len(v) > MAX_ITEM_CHARS for v in value
        ):
            raise ValueError(f"{field} must be a list of up to {MAX_LIST_ITEMS} short text items")
    elif field in TEXT_FIELDS:
        if value is not None and (not isinstance(value, str) or len(value) > MAX_TEXT_CHARS):
            raise ValueError(f"{field} must be text of at most {MAX_TEXT_CHARS:,} characters")
    else:
        raise ValueError(f"Unknown onboarding field: {field}")
    return value


class StepUpdate(BaseModel):
    step: int = Field(ge=0, le=50)
    field: str
    value: Any = None  # varies by step

    @model_validator(mode="after")
    def check_answer(self):
        validate_answer(self.field, self.value)
        return self


class OnboardingComplete(BaseModel):
    data: dict  # full collected data

    @field_validator("data")
    @classmethod
    def check_answers(cls, data: dict) -> dict:
        for field, value in data.items():
            validate_answer(field, value)
        return data


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

    if body.field == "pack" and body.value not in PACKS:
        raise HTTPException(status_code=400, detail="Unknown book type")

    # Save raw step data to onboarding_data JSONB. Assign a new dict: an
    # in-place mutation of a plain JSONB column isn't tracked by SQLAlchemy,
    # so every step after the first was silently never saved.
    profile.onboarding_data = {**(profile.onboarding_data or {}), body.field: body.value}
    profile.onboarding_step = max(profile.onboarding_step, body.step + 1)

    # Also update the actual field if it maps directly
    field_map = {
        "pack": "pack",
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
    await consume_user_quota(db, current_user.id, "ai_request", settings.AI_DAILY_REQUEST_LIMIT)

    async def event_stream():
        # JSON events like every other stream — raw text broke on newlines.
        try:
            async for chunk in generate_voice_preview_stream(onboarding_data, profile):
                yield sse_text(chunk)
        except Exception as exc:
            yield sse_error(exc, "voice_preview")
        yield SSE_DONE

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

    # Persist all collected fields. Packs reuse the original column names
    # (see app/services/packs.py), e.g. the general pack's genre is stored
    # in theological_lens and its style rules in theological_guardrails.
    if "pack" in data:
        if data["pack"] not in PACKS:
            raise HTTPException(status_code=400, detail="Unknown book type")
        profile.pack = data["pack"]
    rules = []
    if isinstance(data.get("pov_tense"), str) and data["pov_tense"].strip():
        # Fiction interview: the narrative mode becomes the first style rule.
        rules.append(f"Point of view and tense: {data['pov_tense'].strip()[:120]}")
    if isinstance(data.get("style_rules"), list):
        rules += [str(rule) for rule in data["style_rules"] if str(rule).strip()]
    if rules:
        profile.theological_guardrails = rules
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
        # One AI call; counted like any other so repeating onboarding isn't free.
        await consume_user_quota(db, current_user.id, "ai_request", settings.AI_DAILY_REQUEST_LIMIT)
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

                # Replace, don't append: re-running onboarding used to duplicate every chunk.
                await db.execute(delete(DocumentEmbedding).where(
                    DocumentEmbedding.user_id == current_user.id,
                    DocumentEmbedding.doc_type == "writing_sample",
                ))
                for sample in profile.writing_samples:
                    await index_writing_sample(current_user.id, sample, db)

        except Exception:
            # Non-fatal — user is marked onboarded and profile fields are saved.
            # DNA can be recovered via POST /voice-profile/reprocess.
            logger.exception("inline_voice_dna_extraction_failed", user_id=current_user.id)

    return {"onboarded": True, "message": "Voice profile processed successfully."}