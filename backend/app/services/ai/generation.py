"""
Voice Brief Builder — the architectural core of The Scribe.

Every generation request runs through this service.
It compiles a personalized "ghost brief" from the author's voice profile,
retrieving only the most relevant samples and testimonies via pgvector similarity search.
"""
import time
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models import VoiceProfile, DocumentEmbedding, Testimony, Scripture, Chapter
from app.services.voice.embeddings import EmbeddingService
from app.services.ai.llm_client import get_llm_client, estimate_cost
from app.services.ai.json_utils import strip_json_fences

import structlog

logger = structlog.get_logger()


embedding_service = EmbeddingService()


def _cadence_description(score: float) -> str:
    if score < 0.3:
        return "short, punchy, declarative sentences — direct address, staccato rhythm"
    elif score < 0.6:
        return "balanced cadence — mixes short declarations with longer explanatory sentences"
    else:
        return "flowing, expansive sentences — layered clauses, builds toward a declaration"


async def build_voice_brief(profile: VoiceProfile, chapter_context: Optional[str] = None) -> str:
    """
    Build the personalized ghost brief injected into every generation.
    """
    cadence = _cadence_description(profile.cadence_score or 0.5)
    scriptures = profile.anchor_scriptures or []
    top_scriptures = [s["ref"] for s in scriptures[:8]] if scriptures else []
    phrases = profile.signature_phrases or []
    tags = profile.style_tags or []
    tones = profile.tone_preferences or []
    translation = profile.preferred_translation or "NKJV"

    samples_text = ""
    if profile.writing_samples:
        samples = profile.writing_samples[:2]
        samples_text = "\n---\n".join(samples[:1500])  # cap context

    brief = f"""You are ghostwriting for a Christian author. Study everything below and write ONLY in their voice.

═══════════════════════════════════════
VOICE BRIEF
═══════════════════════════════════════

THEOLOGICAL LENS: {profile.theological_lens or 'Spirit-filled'}
MINISTRY BACKGROUND: {profile.ministry_background or 'Not specified'}
TARGET AUDIENCE: {profile.target_audience or 'Believers seeking deeper faith'}
PREFERRED BIBLE TRANSLATION: {translation}

WRITING TONES (ranked by prominence):
{chr(10).join(f'  • {t}' for t in tones) if tones else '  • teaching, exhortation'}

CADENCE & RHYTHM:
  {cadence}

SIGNATURE PHRASES (use naturally — never force, never repeat back-to-back):
{chr(10).join(f'  • "{p}"' for p in phrases[:10]) if phrases else '  • (none captured yet)'}

STYLE CHARACTERISTICS:
{chr(10).join(f'  • {t}' for t in tags) if tags else '  • (none captured yet)'}

ANCHOR SCRIPTURES (cite only these or verified scripture — never hallucinate references):
{chr(10).join(f'  • {r}' for r in top_scriptures) if top_scriptures else '  • (none specified)'}

VOICE SUMMARY (your internal compass for this author):
{profile.voice_summary or 'No voice summary yet — use all available signals above.'}
"""

    if samples_text:
        brief += f"""
WRITING SAMPLES (study rhythm, paragraph length, vocabulary, opening hooks):
═══════════════════════════════════════
{samples_text[:3000]}
═══════════════════════════════════════
"""

    if chapter_context:
        brief += f"\nCHAPTER CONTEXT FROM PRIOR CHAPTERS (maintain doctrinal consistency):\n{chapter_context}\n"

    brief += """
═══════════════════════════════════════
RULES:
1. Never break voice. Every sentence must sound like this author wrote it.
2. Never cite a scripture not in the anchor list or verified index — hallucinated refs destroy trust.
3. Never use generic Christian phrases that don't appear in their samples.
4. Match their paragraph length, hook style, and closing cadence.
5. If they use rhetorical questions — use them. If they don't — don't.
═══════════════════════════════════════
"""
    return brief


async def retrieve_relevant_context(
    user_id: str,
    query: str,
    db: AsyncSession,
    top_k_samples: int = 3,
    top_k_testimonies: int = 2,
) -> dict:
    """
    RAG retrieval: find the most relevant writing samples and testimonies
    for a given chapter query using pgvector similarity search.
    """
    query_embedding = await embedding_service.embed(query)

    # Vector similarity search on writing samples
    sample_results = await db.execute(
        text("""
            SELECT content, 1 - (embedding <=> :embedding) AS similarity
            FROM document_embeddings
            WHERE user_id = :user_id AND doc_type = 'writing_sample'
            ORDER BY embedding <=> :embedding
            LIMIT :k
        """),
        {"embedding": str(query_embedding), "user_id": user_id, "k": top_k_samples}
    )
    samples = [row[0] for row in sample_results.fetchall()]

    # Vector similarity search on testimonies
    testimony_results = await db.execute(
        text("""
            SELECT de.content, de.source_id, 1 - (de.embedding <=> :embedding) AS similarity
            FROM document_embeddings de
            WHERE de.user_id = :user_id AND de.doc_type = 'testimony'
            ORDER BY de.embedding <=> :embedding
            LIMIT :k
        """),
        {"embedding": str(query_embedding), "user_id": user_id, "k": top_k_testimonies}
    )
    testimony_rows = testimony_results.fetchall()

    # Fetch full testimony texts
    testimony_ids = [row[1] for row in testimony_rows if row[1]]
    testimonies = []
    if testimony_ids:
        t_result = await db.execute(
            select(Testimony).where(Testimony.id.in_(testimony_ids))
        )
        testimonies = [t.story for t in t_result.scalars().all()]

    return {"samples": samples, "testimonies": testimonies}


async def get_chapter_memory(project_id: str, before_chapter_number: int, db: AsyncSession) -> str:
    """
    Retrieve summaries of all prior chapters for continuity memory.
    """
    result = await db.execute(
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .where(Chapter.chapter_number < before_chapter_number)
        .where(Chapter.summary.isnot(None))
        .order_by(Chapter.chapter_number)
    )
    chapters = result.scalars().all()
    if not chapters:
        return ""

    memory = "PRIOR CHAPTER SUMMARIES:\n"
    for ch in chapters:
        memory += f"\nChapter {ch.chapter_number} — {ch.title}:\n{ch.summary}\n"
    return memory


async def generate_chapter_stream(
    profile: VoiceProfile,
    chapter,
    project,
    db: AsyncSession,
):
    """
    Main chapter generation — streams Claude output token by token.
    Injects: voice brief + RAG context + chapter memory + chapter brief.
    """
    start_time = time.time()

    # Build chapter query for RAG
    rag_query = f"{chapter.intent or chapter.title} {' '.join(chapter.key_points or [])}"

    # Retrieve relevant context via embeddings
    context = await retrieve_relevant_context(
        user_id=profile.user_id,
        query=rag_query,
        db=db,
    )

    # Get chapter memory (prior chapters)
    chapter_memory = await get_chapter_memory(project.id, chapter.chapter_number, db)

    # Build voice brief
    voice_brief = await build_voice_brief(profile, chapter_context=chapter_memory)

    # Build chapter brief
    testimonies_text = "\n\n".join(context["testimonies"]) if context["testimonies"] else "None retrieved."
    relevant_samples = "\n---\n".join(context["samples"]) if context["samples"] else ""

    chapter_prompt = f"""{voice_brief}

════════════════════════════════════════
MANUSCRIPT CONTEXT
════════════════════════════════════════
Book Title: {project.title}
Book Theme: {project.theme or 'Not specified'}
Genre: {project.genre or 'teaching'}

════════════════════════════════════════
THIS CHAPTER BRIEF
════════════════════════════════════════
Chapter {chapter.chapter_number}: {chapter.title}

Intent (what this chapter must accomplish):
{chapter.intent or 'Not specified'}

Key Points to Cover:
{chr(10).join(f'  {i+1}. {p}' for i, p in enumerate(chapter.key_points or []))}

Anchor Scriptures for This Chapter:
{chr(10).join(f'  • {s}' for s in (chapter.anchor_scriptures or []))}

Personal Story/Testimony to Weave In:
{testimonies_text}

Relevant Writing Style References (retrieved):
{relevant_samples[:1500] if relevant_samples else '(none retrieved)'}

════════════════════════════════════════
GENERATION INSTRUCTIONS
════════════════════════════════════════
Write the full chapter draft. Target 1,500–2,500 words.
- Open with a strong hook in this author's exact voice
- Weave the testimony naturally — not as an insert but as revelation
- Anchor each major point to scripture (from the list above only)
- Close with an invitation, declaration, or prophetic charge — consistent with their style
- Use their signature phrases naturally, not mechanically
"""

    llm = get_llm_client()

    async for chunk in llm.stream(
        messages=[{"role": "user", "content": chapter_prompt}],
        max_tokens=4000,
    ):
        yield chunk

    usage = llm.last_usage
    latency_ms = int((time.time() - start_time) * 1000)
    cost_usd = estimate_cost(llm.provider, usage) if usage else 0.0
    tokens_in = usage.input_tokens if usage else 0
    tokens_out = usage.output_tokens if usage else 0

    # Yield metadata sentinel for the route handler to capture
    yield f"\n\n[META:tokens_in={tokens_in},tokens_out={tokens_out},cost={cost_usd:.6f},latency={latency_ms},provider={llm.provider}]"


async def generate_voice_preview_stream(onboarding_data: dict, profile: Optional[VoiceProfile] = None):
    """
    Live voice preview during onboarding.
    Streams a 150-word sample paragraph showing the emerging voice.
    """
    lens = onboarding_data.get("theological_lens", "spirit-filled")
    bg = onboarding_data.get("ministry_background", "")
    phrases = onboarding_data.get("signature_phrases", [])
    samples = onboarding_data.get("writing_samples", [])
    tone = onboarding_data.get("tone_preferences", ["teaching"])

    sample_text = samples[0][:800] if samples else ""
    phrases_text = ", ".join(f'"{p}"' for p in phrases[:5]) if phrases else "none yet"

    prompt = f"""You are learning to write in the voice of a Christian author.

Based on this partial profile:
- Theological lens: {lens}
- Ministry background: {bg[:200] if bg else 'not specified'}
- Signature phrases: {phrases_text}
- Tone: {', '.join(tone) if isinstance(tone, list) else tone}
{f'- Writing sample excerpt: "{sample_text}"' if sample_text else ''}

Write a single vivid paragraph (120–150 words) as a preview of this author's voice.
Pick a topic: the moment God calls someone into their purpose.
Make it feel distinctly like THIS author — not generic Christian writing.
No preamble. Just the paragraph."""

    llm = get_llm_client()
    async for chunk in llm.stream(messages=[{"role": "user", "content": prompt}], max_tokens=300):
        yield chunk


async def extract_voice_dna(profile: VoiceProfile, db: AsyncSession) -> dict:
    """
    Background job: extract voice DNA from writing samples.
    Returns structured voice data to update the profile.
    """
    samples = profile.writing_samples or []
    if not samples:
        return {}

    combined = "\n\n---\n\n".join(samples[:5])

    prompt = f"""Analyze these writing samples from a Christian author and extract their voice DNA.

WRITING SAMPLES:
{combined[:4000]}

Return a JSON object with exactly these keys:
{{
  "signature_phrases": ["list of 8-12 distinctive recurring phrases or sentence openers"],
  "cadence_score": 0.0,  // 0.0 = very punchy/short sentences, 1.0 = very flowing/long sentences
  "style_tags": ["list of 6-8 style characteristics like: rhetorical_questions, direct_address, repetition_for_emphasis, declarative_statements, scripture_integration, narrative_testimony, etc"],
  "voice_summary": "300-word description of this author's voice that a ghostwriter could use as a compass",
  "anchor_scriptures": [
    {{"ref": "Isaiah 61:1", "themes": ["calling", "healing"]}}
  ]
}}

Return ONLY valid JSON. No markdown, no explanation."""

    llm = get_llm_client()
    result = await llm.complete(messages=[{"role": "user", "content": prompt}], max_tokens=2000)

    import json
    raw = result.text.strip()
    try:
        text = strip_json_fences(raw)
        return json.loads(text)
    except Exception as e:
        logger.warning(
            "voice_dna_extraction_parse_failed",
            user_id=profile.user_id,
            error=str(e),
            raw_response_preview=raw[:300],
        )
        return {}


async def generate_chapter_summary(content: str, title: str) -> str:
    """Generate a concise summary of a chapter for chapter memory."""
    prompt = f"""Summarize this chapter for use as context in subsequent chapter generation.
Capture: main theological argument, key scriptures cited, any testimony/story used, closing declaration.
Keep to 150 words max.

Chapter: {title}
Content: {content[:3000]}"""

    llm = get_llm_client()
    result = await llm.complete(messages=[{"role": "user", "content": prompt}], max_tokens=300)
    return result.text


async def score_voice_match(content: str, profile: VoiceProfile) -> float:
    """
    Score how well a piece of text matches the author's voice.
    Returns 0.0–1.0 using embedding cosine similarity against their corpus.
    """
    if not profile.voice_summary:
        return 0.75  # default when no baseline

    content_embedding = await embedding_service.embed(content[:1000])
    voice_embedding = await embedding_service.embed(profile.voice_summary)

    # Cosine similarity
    import numpy as np
    a = np.array(content_embedding)
    b = np.array(voice_embedding)
    similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    # Scale to 0.5–1.0 range (cosine sim on text is rarely below 0.5)
    return round(min(1.0, max(0.0, (similarity + 1) / 2)), 3)
