"""
Manuscript Companion Chat — a whole-book-aware AI assistant.

Unlike the chapter-scoped /generate/chat (which only knows the voice brief
and the current chapter), this assistant retrieves across EVERY chapter in
a project via pgvector (DocumentEmbedding doc_type='chapter') and combines
that with a structural manifest of all chapters (title, status, scriptures,
key points) — so it can answer both semantic questions ("have I covered
this idea?") and structural ones ("which chapter discusses X?", "where have
I used this scripture before?") even when the literal wording doesn't match
well enough for vector search alone to find it.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models import Project, Chapter, CompanionChatMessage, VoiceProfile
from app.services.voice.embeddings import embedding_service
from app.services.ai.llm_client import get_llm_client


async def _build_chapter_manifest(project_id: str, db: AsyncSession) -> str:
    """
    A compact structural index of every chapter — title, status, word count,
    anchor scriptures, key points. This alone answers a surprising number of
    companion-chat questions without needing semantic retrieval at all, and
    it's cheap (one query, small payload).
    """
    result = await db.execute(
        select(Chapter).where(Chapter.project_id == project_id).order_by(Chapter.position)
    )
    chapters = result.scalars().all()

    if not chapters:
        return "This manuscript has no chapters yet."

    lines = []
    for ch in chapters:
        scriptures = ", ".join(ch.anchor_scriptures or []) or "none"
        points = "; ".join((ch.key_points or [])[:4]) or "none specified"
        lines.append(
            f"Chapter {ch.chapter_number}: \"{ch.title}\" "
            f"[{ch.status}, {ch.word_count} words] — "
            f"scriptures: {scriptures} — key points: {points}"
        )
    return "\n".join(lines)


async def _retrieve_relevant_chapter_excerpts(
    project_id: str, query: str, db: AsyncSession, top_k: int = 6
) -> list[dict]:
    """
    pgvector similarity search scoped to this project's indexed chapter
    content. Returns the chunk text plus which chapter it came from, so the
    LLM (and the UI) can cite sources.
    """
    query_embedding = await embedding_service.embed(query)

    result = await db.execute(
        text("""
            SELECT de.content, de.source_id, 1 - (de.embedding <=> :embedding) AS similarity
            FROM document_embeddings de
            WHERE de.project_id = :project_id AND de.doc_type = 'chapter'
            ORDER BY de.embedding <=> :embedding
            LIMIT :k
        """),
        {"embedding": str(query_embedding), "project_id": project_id, "k": top_k},
    )
    rows = result.fetchall()
    if not rows:
        return []

    chapter_ids = list({row[1] for row in rows if row[1]})
    ch_result = await db.execute(select(Chapter).where(Chapter.id.in_(chapter_ids)))
    chapters_by_id = {c.id: c for c in ch_result.scalars().all()}

    excerpts = []
    for content, source_id, similarity in rows:
        ch = chapters_by_id.get(source_id)
        excerpts.append({
            "chapter_id": source_id,
            "chapter_number": ch.chapter_number if ch else None,
            "chapter_title": ch.title if ch else "Unknown chapter",
            "content": content,
            "similarity": float(similarity),
        })
    return excerpts


async def companion_chat_stream(
    project_id: str,
    user_message: str,
    history: list[dict],
    db: AsyncSession,
):
    """
    Stream a Manuscript Companion Chat answer, grounded in:
      - a structural manifest of all chapters (always included — cheap, high value)
      - semantically retrieved chapter excerpts relevant to this message
      - the author's voice profile (so the assistant's own writing matches them)

    Yields text chunks, then a final sentinel with the chapter IDs cited.
    """
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        yield "I couldn't find that manuscript."
        return

    profile_result = await db.execute(select(VoiceProfile).where(VoiceProfile.user_id == project.user_id))
    profile = profile_result.scalar_one_or_none()

    manifest = await _build_chapter_manifest(project_id, db)
    excerpts = await _retrieve_relevant_chapter_excerpts(project_id, user_message, db)

    excerpts_text = "\n\n".join(
        f"[Chapter {e['chapter_number']}: \"{e['chapter_title']}\"]\n{e['content']}"
        for e in excerpts
    ) if excerpts else "(No closely matching passages found — answer from the chapter manifest below if possible, and say so if you genuinely don't know.)"

    voice_note = ""
    if profile and profile.voice_summary:
        voice_note = f"\nThe author's voice (for your own tone when answering): {profile.voice_summary[:400]}"

    system = f"""You are the Manuscript Companion for "{project.title}" — an AI that has read this \
entire book-in-progress and helps the author understand their own manuscript.

THEME: {project.theme or 'not specified'}
GENRE: {project.genre or 'not specified'}

CHAPTER MANIFEST (every chapter in this manuscript):
{manifest}

RELEVANT PASSAGES (retrieved for this specific question):
{excerpts_text}
{voice_note}

You answer questions like:
- "Have I already covered this idea?" — check both the manifest and the passages.
- "Which chapter discusses X?" — point to specific chapter numbers and titles.
- "Am I repeating myself?" — compare passages/chapters for overlapping content.
- "Where have I used this scripture before?" — check the manifest's scripture lists AND search the passages.

Be specific and cite chapter numbers/titles when you reference content. If something
genuinely isn't in the manifest or retrieved passages, say so plainly rather than guessing —
do not invent chapter content that wasn't shown to you above."""

    messages = [{"role": m["role"], "content": m["content"]} for m in history[-10:]]
    messages.append({"role": "user", "content": user_message})

    llm = get_llm_client()
    async for chunk in llm.stream(messages=messages, system=system, max_tokens=900):
        yield chunk

    cited_ids = list({e["chapter_id"] for e in excerpts if e["chapter_id"]})
    yield f"\n\n[CITED:{','.join(cited_ids)}]"


async def save_message(
    project_id: str,
    user_id: str,
    role: str,
    content: str,
    db: AsyncSession,
    referenced_chapter_ids: Optional[list[str]] = None,
) -> CompanionChatMessage:
    msg = CompanionChatMessage(
        project_id=project_id,
        user_id=user_id,
        role=role,
        content=content,
        referenced_chapter_ids=referenced_chapter_ids or [],
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_history(project_id: str, db: AsyncSession, limit: int = 50) -> list[CompanionChatMessage]:
    result = await db.execute(
        select(CompanionChatMessage)
        .where(CompanionChatMessage.project_id == project_id)
        .order_by(CompanionChatMessage.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())
