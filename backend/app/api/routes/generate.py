"""
AI Generation routes — all return SSE streams.
Powers: chapter generation, continue writing, weave story, voice check, scripture suggest, chat.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
import json

from app.db.session import get_db
from app.models import User, VoiceProfile, Testimony, GenerationLog
from app.core.security import get_current_user
from app.api.ownership import get_owned_chapter, get_owned_project
from app.services.ai.generation import (
    generate_chapter_stream,
    analyze_voice_drift,
    build_voice_brief,
)
from app.services.ai.llm_client import get_llm_client
from app.services.scripture_lookup import fetch_scripture_text
from app.core.config import settings
from app.services.security.rate_limits import consume_user_quota

router = APIRouter(prefix="/generate", tags=["generation"])


async def _get_profile(user_id: str, db: AsyncSession) -> VoiceProfile:
    result = await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Voice profile not found. Complete onboarding first.")
    return profile


class GenerateChapterRequest(BaseModel):
    chapter_id: str


class ContinueRequest(BaseModel):
    chapter_id: str
    cursor_text: str = Field(max_length=12_000)  # text up to cursor position
    instruction: Optional[str] = Field(default=None, max_length=1_000)


class WeaveStoryRequest(BaseModel):
    chapter_id: str
    testimony_id: str
    cursor_text: str = Field(max_length=12_000)


class VoiceCheckRequest(BaseModel):
    chapter_id: str
    text: str = Field(max_length=30_000)


class ScriptureSuggestRequest(BaseModel):
    chapter_id: str
    context: str = Field(max_length=5_000)  # current paragraph or chapter theme


class ChatRequest(BaseModel):
    chapter_id: str
    message: str = Field(min_length=1, max_length=5_000)
    history: Optional[List[dict]] = Field(default=None, max_length=10)


async def _consume_ai_request(user_id: str, db: AsyncSession) -> None:
    await consume_user_quota(db, user_id, "ai_request", settings.AI_DAILY_REQUEST_LIMIT)


# ─────────────────────────────────────────────
# Full chapter generation
# ─────────────────────────────────────────────
@router.post("/chapter")
async def generate_chapter(
    body: GenerateChapterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await get_owned_chapter(body.chapter_id, current_user.id, db)
    project = await get_owned_project(chapter.project_id, current_user.id, db)
    profile = await _get_profile(current_user.id, db)
    await _consume_ai_request(current_user.id, db)

    log = GenerationLog(user_id=current_user.id, chapter_id=chapter.id, action="generate_chapter", model=settings.LLM_PROVIDER)
    db.add(log)

    async def stream():
        buffer = []
        try:
            async for chunk in generate_chapter_stream(profile, chapter, project, db):
                if chunk.startswith("\n\n[META:"):
                    # Parse metadata sentinel
                    meta_str = chunk.replace("\n\n[META:", "").rstrip("]")
                    meta = dict(kv.split("=") for kv in meta_str.split(","))
                    log.tokens_in = int(meta.get("tokens_in", 0))
                    log.tokens_out = int(meta.get("tokens_out", 0))
                    log.cost_usd = float(meta.get("cost", 0))
                    log.latency_ms = int(meta.get("latency", 0))
                    log.model = meta.get("provider", settings.LLM_PROVIDER)
                    log.success = True
                    await db.commit()
                else:
                    buffer.append(chunk)
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
        except Exception as e:
            log.success = False
            log.error_message = str(e)
            await db.commit()
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

        # Auto-update chapter status
        if buffer:
            chapter.status = "in_progress"
            await db.commit()

    return StreamingResponse(stream(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# Continue writing from cursor
# ─────────────────────────────────────────────
@router.post("/continue")
async def continue_writing(
    body: ContinueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_chapter(body.chapter_id, current_user.id, db)
    profile = await _get_profile(current_user.id, db)
    await _consume_ai_request(current_user.id, db)
    voice_brief = await build_voice_brief(profile)

    prompt = f"""{voice_brief}

Continue the following passage naturally in this author's voice.
{f'Instruction: {body.instruction}' if body.instruction else ''}
Pick up seamlessly — do not repeat the last sentence.

...{body.cursor_text[-500:]}"""

    async def stream():
        llm = get_llm_client()
        async for chunk in llm.stream(messages=[{"role": "user", "content": prompt}], max_tokens=800):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# Weave testimony into text
# ─────────────────────────────────────────────
@router.post("/weave-story")
async def weave_story(
    body: WeaveStoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_chapter(body.chapter_id, current_user.id, db)
    profile = await _get_profile(current_user.id, db)

    result = await db.execute(select(Testimony).where(Testimony.id == body.testimony_id, Testimony.user_id == current_user.id))
    testimony = result.scalar_one_or_none()
    if not testimony:
        raise HTTPException(status_code=404, detail="Testimony not found")

    voice_brief = await build_voice_brief(profile)
    await _consume_ai_request(current_user.id, db)

    prompt = f"""{voice_brief}

The author wants to weave this personal testimony into their writing:

TESTIMONY:
{testimony.story}

CURRENT TEXT (insert after or integrate into):
...{body.cursor_text[-600:]}

Naturally integrate or transition to the testimony. It should feel like revelation, not an insert.
Write in the author's exact voice. 200–400 words."""

    async def stream():
        llm = get_llm_client()
        async for chunk in llm.stream(messages=[{"role": "user", "content": prompt}], max_tokens=600):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# Voice drift check
# ─────────────────────────────────────────────
@router.post("/voice-check")
async def voice_check(
    body: VoiceCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    chapter = await get_owned_chapter(body.chapter_id, current_user.id, db)
    profile = await _get_profile(current_user.id, db)
    await _consume_ai_request(current_user.id, db)
    analysis = await analyze_voice_drift(body.text, profile, db)
    score = analysis["overall_score"]

    # Also get LLM feedback on what's off
    if score < 0.75:
        prompt = f"""This author has these voice characteristics:
- Signature phrases: {', '.join((profile.signature_phrases or [])[:5])}
- Cadence: {profile.cadence_score or 0.5}
- Style: {', '.join((profile.style_tags or [])[:4])}

Review this passage and identify 2-3 specific phrases or sentences that don't sound like them.
Be specific and brief.

Passage:
{body.text[:800]}"""

        llm = get_llm_client()
        result = await llm.complete(messages=[{"role": "user", "content": prompt}], max_tokens=300)
        feedback = result.text
    else:
        feedback = "This passage is strongly in your voice."

    # Update chapter voice match score (latest snapshot) and log this check
    # as a GenerationLog row so Voice Drift Analytics has historical trend
    # data to chart — previously this route updated the chapter but never
    # wrote a log row, so no trend could ever be computed.
    chapter.voice_match_score = score

    log = GenerationLog(
        user_id=current_user.id,
        chapter_id=body.chapter_id,
        action="voice_check",
        model=settings.LLM_PROVIDER,
        voice_match_score=score,
        success=True,
    )
    db.add(log)
    await db.commit()

    return {
        "voice_match_score": score,
        "grade": "Excellent" if score >= 0.9 else "Strong" if score >= 0.8 else "Good" if score >= 0.7 else "Needs work",
        "feedback": feedback,
        "cadence_score": analysis["cadence_score"],
        "cadence_delta": analysis["cadence_delta"],
        "phrase_matches": analysis["phrase_matches"],
        "phrase_usage_rate": analysis["phrase_usage_rate"],
        "scripture_matches": analysis["scripture_matches"],
    }


# ─────────────────────────────────────────────
# Scripture suggestion
# ─────────────────────────────────────────────
@router.post("/scripture-suggest")
async def scripture_suggest(
    body: ScriptureSuggestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_chapter(body.chapter_id, current_user.id, db)
    profile = await _get_profile(current_user.id, db)
    await _consume_ai_request(current_user.id, db)
    anchor = [s["ref"] for s in (profile.anchor_scriptures or [])][:10]
    translation = profile.preferred_translation or "NKJV"

    prompt = f"""Suggest 5 relevant Bible scriptures for this writing context.

Context: {body.context[:500]}
Author's preferred translation: {translation}
Author's anchor scriptures (prioritize these if relevant): {', '.join(anchor) if anchor else 'none'}

Return JSON array: [{{"ref": "Book Chapter:Verse", "reason": "why this fits"}}]
Each reference is checked against a real scripture database afterward and its actual verse
text is used, not anything you write here, so do not include a "text" field. Any reference
that fails to verify is discarded, so suggest more candidates than you're fully confident
about. Return ONLY valid JSON."""

    llm = get_llm_client()
    result = await llm.complete(messages=[{"role": "user", "content": prompt}], max_tokens=500)

    try:
        clean = result.text.strip().replace("```json", "").replace("```", "")
        candidates = json.loads(clean)
    except Exception:
        candidates = []

    suggestions = []
    for c in candidates:
        if not isinstance(c, dict) or not c.get("ref"):
            continue
        verified = await fetch_scripture_text(c["ref"], translation, db)
        if verified is None:
            continue
        suggestions.append({"ref": verified["ref"], "text": verified["text"], "reason": c.get("reason", "")})
        if len(suggestions) >= 3:
            break

    return {"suggestions": suggestions}


# ─────────────────────────────────────────────
# Freeform Scribe AI chat
# ─────────────────────────────────────────────
@router.post("/chat")
async def scribe_chat(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_chapter(body.chapter_id, current_user.id, db)
    profile = await _get_profile(current_user.id, db)
    await _consume_ai_request(current_user.id, db)
    voice_brief = await build_voice_brief(profile)

    system = f"""{voice_brief}

You are The Scribe — an AI writing assistant built specifically for this author.
You help them write their book in their own voice. You know them deeply.
When they ask you to write, write in their voice. When they ask questions, be their creative partner.
Be direct, warm, and ministerially aware."""

    messages = body.history[-10:] if body.history else []
    messages.append({"role": "user", "content": body.message})

    async def stream():
        llm = get_llm_client()
        async for chunk in llm.stream(messages=messages, system=system, max_tokens=1000):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
