"""
AI Generation routes — all return SSE streams.
Powers: chapter generation, continue writing, weave story, voice check, scripture suggest, chat.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
import json
import time

from app.db.session import get_db
from app.models import User, VoiceProfile, Chapter, Project, Testimony, GenerationLog
from app.core.security import get_current_user
from app.services.ai.generation import (
    generate_chapter_stream,
    score_voice_match,
    build_voice_brief,
    get_chapter_memory,
)
from app.core.config import settings
from anthropic import AsyncAnthropic

router = APIRouter(prefix="/generate", tags=["generation"])
client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

INPUT_COST = 0.000003
OUTPUT_COST = 0.000015


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
    cursor_text: str  # text up to cursor position
    instruction: Optional[str] = None


class WeaveStoryRequest(BaseModel):
    chapter_id: str
    testimony_id: str
    cursor_text: str


class VoiceCheckRequest(BaseModel):
    chapter_id: str
    text: str


class ScriptureSuggestRequest(BaseModel):
    chapter_id: str
    context: str  # current paragraph or chapter theme


class ChatRequest(BaseModel):
    chapter_id: str
    message: str
    history: Optional[List[dict]] = []


# ─────────────────────────────────────────────
# Full chapter generation
# ─────────────────────────────────────────────
@router.post("/chapter")
async def generate_chapter(
    body: GenerateChapterRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await _get_profile(current_user.id, db)

    result = await db.execute(select(Chapter).where(Chapter.id == body.chapter_id, Chapter.user_id == current_user.id))
    chapter = result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    result = await db.execute(select(Project).where(Project.id == chapter.project_id))
    project = result.scalar_one_or_none()

    start_time = time.time()
    log = GenerationLog(user_id=current_user.id, chapter_id=chapter.id, action="generate_chapter", model="claude-sonnet-4-20250514")
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
    profile = await _get_profile(current_user.id, db)
    voice_brief = await build_voice_brief(profile)

    prompt = f"""{voice_brief}

Continue the following passage naturally in this author's voice.
{f'Instruction: {body.instruction}' if body.instruction else ''}
Pick up seamlessly — do not repeat the last sentence.

...{body.cursor_text[-500:]}"""

    async def stream():
        async with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        ) as s:
            async for text in s.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
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
    profile = await _get_profile(current_user.id, db)

    result = await db.execute(select(Testimony).where(Testimony.id == body.testimony_id, Testimony.user_id == current_user.id))
    testimony = result.scalar_one_or_none()
    if not testimony:
        raise HTTPException(status_code=404, detail="Testimony not found")

    voice_brief = await build_voice_brief(profile)

    prompt = f"""{voice_brief}

The author wants to weave this personal testimony into their writing:

TESTIMONY:
{testimony.story}

CURRENT TEXT (insert after or integrate into):
...{body.cursor_text[-600:]}

Naturally integrate or transition to the testimony. It should feel like revelation, not an insert.
Write in the author's exact voice. 200–400 words."""

    async def stream():
        async with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        ) as s:
            async for text in s.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
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
    profile = await _get_profile(current_user.id, db)
    score = await score_voice_match(body.text, profile)

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

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        feedback = response.content[0].text
    else:
        feedback = "This passage is strongly in your voice."

    # Update chapter voice match score
    result = await db.execute(select(Chapter).where(Chapter.id == body.chapter_id))
    chapter = result.scalar_one_or_none()
    if chapter:
        chapter.voice_match_score = score
        await db.commit()

    return {
        "voice_match_score": score,
        "grade": "Excellent" if score >= 0.9 else "Strong" if score >= 0.8 else "Good" if score >= 0.7 else "Needs work",
        "feedback": feedback,
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
    profile = await _get_profile(current_user.id, db)
    anchor = [s["ref"] for s in (profile.anchor_scriptures or [])][:10]
    translation = profile.preferred_translation or "NKJV"

    prompt = f"""Suggest 3 relevant Bible scriptures for this writing context.

Context: {body.context[:500]}
Author's preferred translation: {translation}
Author's anchor scriptures (prioritize these if relevant): {', '.join(anchor) if anchor else 'none'}

Return JSON array: [{{"ref": "Book Chapter:Verse", "text": "verse text in {translation}", "reason": "why this fits"}}]
Only verified scriptures. No hallucinated references. Return ONLY valid JSON."""

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    import json as json_mod
    try:
        clean = response.content[0].text.strip().replace("```json", "").replace("```", "")
        suggestions = json_mod.loads(clean)
    except Exception:
        suggestions = []

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
    profile = await _get_profile(current_user.id, db)
    voice_brief = await build_voice_brief(profile)

    system = f"""{voice_brief}

You are The Scribe — an AI writing assistant built specifically for this author.
You help them write their book in their own voice. You know them deeply.
When they ask you to write, write in their voice. When they ask questions, be their creative partner.
Be direct, warm, and ministerially aware."""

    messages = body.history[-10:] if body.history else []
    messages.append({"role": "user", "content": body.message})

    async def stream():
        async with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system,
            messages=messages,
        ) as s:
            async for text in s.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
