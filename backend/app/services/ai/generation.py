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

from app.models import VoiceProfile, DocumentEmbedding, Testimony, Scripture, Chapter, Project
from app.services.voice.embeddings import EmbeddingService
from app.services.ai.llm_client import get_llm_client, estimate_cost
from app.services.ai.json_utils import strip_json_fences
from app.services.packs import get_pack, pack_for
from app.services.book_bible import book_context
from app.services.ai.voice_enrichment import finalize_dna, voice_dna_prompt

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


async def build_voice_brief(
    profile: VoiceProfile,
    chapter_context: Optional[str] = None,
    project: Optional[Project] = None,
) -> str:
    """
    Build the personalized ghost brief injected into every generation.
    Genre-specific wording comes from the profile's pack (app/services/packs.py).
    When `project` is given, its per-book style overrides the author's
    defaults: its audience replaces theirs, its rules add to theirs.
    """
    pack = pack_for(profile)
    cadence = _cadence_description(profile.cadence_score or 0.5)
    phrases = profile.signature_phrases or []
    tags = profile.style_tags or []
    tones = profile.tone_preferences or []
    book_rules = [r for r in ((project.style_rules if project else None) or []) if isinstance(r, str) and r.strip()]
    rules = (profile.theological_guardrails or []) + book_rules
    audience = (project.target_audience if project else None) or profile.target_audience or pack.default_audience

    samples_text = ""
    if profile.writing_samples:
        samples_text = "\n---\n".join(profile.writing_samples[:2])

    scripture_lines = ""
    if pack.uses_scripture:
        scriptures = profile.anchor_scriptures or []
        top_scriptures = [s["ref"] for s in scriptures[:8]]
        scripture_lines = f"""PREFERRED BIBLE TRANSLATION: {profile.preferred_translation or 'NKJV'}

ANCHOR SCRIPTURES (cite only these or verified scripture — never hallucinate references):
{chr(10).join(f'  • {r}' for r in top_scriptures) if top_scriptures else '  • (none specified)'}
"""

    brief = f"""You are ghostwriting for {pack.author_noun}. Study everything below and write ONLY in their voice.

═══════════════════════════════════════
VOICE BRIEF
═══════════════════════════════════════

{pack.lens_label}: {profile.theological_lens or pack.default_lens}
{pack.background_label}: {profile.ministry_background or 'Not specified'}
TARGET AUDIENCE: {audience}

{pack.rules_label} (never contradict these):
{chr(10).join(f'  • {rule}' for rule in rules) if rules else f'  • {pack.default_rule}'}

WRITING TONES (ranked by prominence):
{chr(10).join(f'  • {t}' for t in tones) if tones else '  • (none specified — infer from samples)'}

CADENCE & RHYTHM:
  {cadence}

SIGNATURE PHRASES (use naturally — never force, never repeat back-to-back):
{chr(10).join(f'  • "{p}"' for p in phrases[:10]) if phrases else '  • (none captured yet)'}

STYLE CHARACTERISTICS:
{chr(10).join(f'  • {t}' for t in tags) if tags else '  • (none captured yet)'}

{scripture_lines}
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

    if project is not None and (project.style_notes or "").strip():
        brief += f"\nSTYLE NOTES FOR THIS BOOK (take precedence over general habits above):\n{project.style_notes.strip()[:2000]}\n"

    if chapter_context:
        brief += f"\nCHAPTER CONTEXT FROM PRIOR CHAPTERS (maintain consistency of ideas, facts and claims):\n{chapter_context}\n"

    brief += f"""
═══════════════════════════════════════
RULES:
1. Never break voice. Every sentence must sound like this author wrote it.
2. {pack.reference_rule}
3. Never use generic stock phrases that don't appear in their samples.
4. Match their paragraph length, hook style, and closing cadence.
5. If they use rhetorical questions — use them. If they don't — don't.
6. Respect the {pack.rules_label.lower()} above. If a request conflicts with them, flag the tension instead of presenting the conflict as this author's view.
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

    # Build voice brief (with this book's style) and the book's own knowledge
    voice_brief = await build_voice_brief(profile, chapter_context=chapter_memory, project=project)
    book_knowledge = await book_context(db, project, rag_query, chapter_id=chapter.id)

    # Build chapter brief
    pack = pack_for(profile)
    testimonies_text = "\n\n".join(context["testimonies"]) if context["testimonies"] else "None retrieved."
    grounding = (
        "- Anchor each major point to scripture (from the list above only)"
        if pack.uses_scripture
        else "- Ground each major point in the key references, stories and samples above — invent nothing"
    )
    relevant_samples = "\n---\n".join(context["samples"]) if context["samples"] else ""

    chapter_prompt = f"""{voice_brief}

════════════════════════════════════════
MANUSCRIPT CONTEXT
════════════════════════════════════════
Book Title: {project.title}
Book Theme: {project.theme or 'Not specified'}
Genre: {project.genre or profile.theological_lens or pack.default_lens}

{book_knowledge or '(No book facts or linked sources yet.)'}

════════════════════════════════════════
THIS CHAPTER BRIEF
════════════════════════════════════════
Chapter {chapter.chapter_number}: {chapter.title}

Intent (what this chapter must accomplish):
{chapter.intent or 'Not specified'}

Key Points to Cover:
{chr(10).join(f'  {i+1}. {p}' for i, p in enumerate(chapter.key_points or []))}

{pack.reference_label} for This Chapter:
{chr(10).join(f'  • {s}' for s in (chapter.anchor_scriptures or [])) or '  • (none specified)'}

{pack.story_label} to Weave In:
{testimonies_text}

Relevant Writing Style References (retrieved):
{relevant_samples[:1500] if relevant_samples else '(none retrieved)'}

════════════════════════════════════════
GENERATION INSTRUCTIONS
════════════════════════════════════════
Write the full chapter draft. Target 1,500–2,500 words.
- Open with a strong hook in this author's exact voice
- Weave the story in naturally — not as an insert but as part of the argument
{grounding}
- {pack.closing_instruction}
- Use their signature phrases naturally, not mechanically
- Stay consistent with the established book facts: names, facts, terms and timeline must match them
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
    # Onboarding saves the chosen pack as a step, before the profile column
    # is finalised, so prefer the in-progress answer.
    pack = get_pack(onboarding_data.get("pack") or getattr(profile, "pack", None))
    lens = onboarding_data.get("theological_lens") or pack.default_lens
    bg = onboarding_data.get("ministry_background", "")
    phrases = onboarding_data.get("signature_phrases", [])
    samples = onboarding_data.get("writing_samples", [])
    tone = onboarding_data.get("tone_preferences") or []

    sample_text = samples[0][:800] if samples else ""
    phrases_text = ", ".join(f'"{p}"' for p in phrases[:5]) if phrases else "none yet"

    prompt = f"""You are learning to write in the voice of {pack.author_noun}.

Based on this partial profile:
- {pack.lens_label.capitalize()}: {lens}
- {pack.background_label.capitalize()}: {bg[:200] if bg else 'not specified'}
- Signature phrases: {phrases_text}
- Tone: {', '.join(tone) if isinstance(tone, list) else tone or 'not specified'}
{f'- Writing sample excerpt: "{sample_text}"' if sample_text else ''}

Write a single vivid paragraph (120–150 words) as a preview of this author's voice.
Pick a topic that suits their genre — for example, {pack.preview_topic}.
Make it feel distinctly like THIS author — not generic writing.
No preamble. Just the paragraph."""

    llm = get_llm_client()
    async for chunk in llm.stream(messages=[{"role": "user", "content": prompt}], max_tokens=300):
        yield chunk


async def extract_voice_dna(profile: VoiceProfile, db: AsyncSession) -> dict:
    """
    Background job: extract voice DNA from writing samples.
    Returns structured voice data to update the profile.

    For packs that use scripture, `anchor_scriptures` in the result is
    verified against the real Scripture index (see finalize_dna).
    """
    samples = profile.writing_samples or []
    if not samples:
        return {}

    combined = "\n\n---\n\n".join(samples[:5])
    prompt = voice_dna_prompt(pack_for(profile), "WRITING SAMPLES", combined[:4000])

    llm = get_llm_client()
    result = await llm.complete(messages=[{"role": "user", "content": prompt}], max_tokens=2000)

    import json
    raw = result.text.strip()
    try:
        text = strip_json_fences(raw)
        dna = json.loads(text)
        return await finalize_dna(dna, pack_for(profile), db)
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

    Kept as a thin wrapper around analyze_voice_drift() for backward
    compatibility with existing callers that only want the headline number.
    """
    analysis = await analyze_voice_drift(content, profile)
    return analysis["overall_score"]


def _text_cadence_score(text: str) -> float:
    """
    Approximate cadence (sentence length/rhythm) on a 0.0 (punchy/short) to
    1.0 (flowing/long) scale, mirroring how cadence_score is described
    elsewhere in the voice profile — used to compare generated text's
    cadence against the author's baseline.
    """
    import re
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    if not sentences:
        return 0.5
    avg_words = sum(len(s.split()) for s in sentences) / len(sentences)
    # 6 words/sentence -> 0.0 (punchy), 28+ words/sentence -> 1.0 (flowing)
    return round(min(1.0, max(0.0, (avg_words - 6) / 22)), 3)


async def analyze_voice_drift(content: str, profile: VoiceProfile, db: Optional[AsyncSession] = None) -> dict:
    """
    Multi-dimensional voice match analysis, broken into the components Voice
    Drift Analytics displays: overall similarity, cadence match, signature
    phrase usage, and anchor scripture usage — not just one blended number.

    Returns:
        {
            "overall_score": float 0-1,
            "cadence_score": float 0-1 (the TEXT's own cadence, comparable to profile.cadence_score),
            "cadence_delta": float (text cadence minus profile baseline cadence; signed),
            "phrase_matches": [phrases from profile.signature_phrases found in content],
            "phrase_usage_rate": float 0-1 (matched / total signature phrases, only meaningful if profile has phrases),
            "scripture_matches": [refs from profile.anchor_scriptures found in content],
        }
    """
    content_lower = content.lower()

    # Overall semantic similarity against the voice summary (unchanged logic)
    overall_score = 0.75
    if profile.voice_summary:
        content_embedding = await embedding_service.embed(content[:1000])
        
        if profile.voice_summary_embedding is not None:
            voice_embedding = profile.voice_summary_embedding
        else:
            voice_embedding = await embedding_service.embed(profile.voice_summary)
            if db is not None:
                profile.voice_summary_embedding = voice_embedding
                db.add(profile)
                await db.commit()

        import numpy as np
        a = np.array(content_embedding)
        b = np.array(voice_embedding)
        similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        overall_score = round(min(1.0, max(0.0, (similarity + 1) / 2)), 3)

    # Cadence: compare the text's own rhythm against the profile's baseline
    text_cadence = _text_cadence_score(content)
    baseline_cadence = profile.cadence_score if profile.cadence_score is not None else 0.5
    cadence_delta = round(text_cadence - baseline_cadence, 3)

    # Signature phrase usage — literal substring match (case-insensitive)
    phrases = profile.signature_phrases or []
    phrase_matches = [p for p in phrases if p.lower() in content_lower]
    phrase_usage_rate = round(len(phrase_matches) / len(phrases), 3) if phrases else None

    # Anchor scripture usage — literal reference match (e.g. "Isaiah 61")
    scriptures = profile.anchor_scriptures or []
    scripture_matches = []
    for s in scriptures:
        ref = s.get("ref", "") if isinstance(s, dict) else str(s)
        # Match on the book+chapter portion so "Isaiah 61:1-3" still matches
        # text that cites "Isaiah 61:2" or similar nearby verses.
        book_chapter = ref.split(":")[0].strip()
        if book_chapter and book_chapter.lower() in content_lower:
            scripture_matches.append(ref)

    return {
        "overall_score": overall_score,
        "cadence_score": text_cadence,
        "cadence_delta": cadence_delta,
        "phrase_matches": phrase_matches,
        "phrase_usage_rate": phrase_usage_rate,
        "scripture_matches": scripture_matches,
    }
