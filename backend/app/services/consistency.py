"""
Consistency checks for a manuscript.

- Repetition (free): near-duplicate passages across chapters, found by
  comparing the chapter chunks already embedded for Companion Chat.
- Book-bible check (one AI call): reads a chapter against the book's
  established facts and lists contradictions. Every reported issue must
  quote the chapter verbatim; issues whose quote isn't actually in the
  chapter are dropped, so the model can't invent problems.
"""
import html
import json
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter
from app.services.ai.json_utils import strip_json_fences
from app.services.ai.llm_client import get_llm_client
from app.services.book_bible import format_entries, format_timeline, relevant_entries, timeline
from app.services.export.docx_export import html_to_plain

REPETITION_THRESHOLD = 0.9
MAX_CHAPTER_CHARS = 12_000


async def find_repeated_passages(db: AsyncSession, project_id: str, *, threshold: float = REPETITION_THRESHOLD, limit: int = 10) -> list[dict]:
    rows = (await db.execute(
        text("""
            SELECT a.source_id, a.content, b.source_id, b.content, 1 - (a.embedding <=> b.embedding) AS similarity
            FROM document_embeddings a
            JOIN document_embeddings b
              ON b.project_id = a.project_id
             AND b.doc_type = 'chapter'
             AND a.source_id < b.source_id
            WHERE a.project_id = :project_id
              AND a.doc_type = 'chapter'
              AND 1 - (a.embedding <=> b.embedding) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """),
        {"project_id": project_id, "threshold": threshold, "limit": limit},
    )).fetchall()
    if not rows:
        return []

    chapter_ids = {r[0] for r in rows} | {r[2] for r in rows}
    chapters = {c.id: c for c in (await db.execute(
        select(Chapter).where(Chapter.id.in_(chapter_ids), Chapter.project_id == project_id)
    )).scalars().all()}

    def ref(chapter_id: str, content: str) -> dict:
        ch = chapters.get(chapter_id)
        return {
            "chapter_id": chapter_id,
            "chapter_number": ch.chapter_number if ch else None,
            "chapter_title": ch.title if ch else "Deleted chapter",
            "excerpt": content[:400],
        }

    return [
        {"similarity": round(float(sim), 3), "a": ref(a_id, a_text), "b": ref(b_id, b_text)}
        for a_id, a_text, b_id, b_text, sim in rows
        if a_id in chapters and b_id in chapters
    ]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def parse_issues(raw: str, chapter_text: str) -> list[dict]:
    """Keep only well-formed issues whose quote really appears in the chapter."""
    try:
        data = json.loads(strip_json_fences(raw))
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []

    haystack = _normalize(chapter_text)
    issues = []
    for item in data:
        if not isinstance(item, dict):
            continue
        quote, issue = str(item.get("quote", "")).strip(), str(item.get("issue", "")).strip()
        if not quote or not issue or _normalize(quote) not in haystack:
            continue
        issues.append({"entry": str(item.get("entry", "")).strip()[:200], "quote": quote[:500], "issue": issue[:600]})
    return issues[:10]


async def check_chapter_against_bible(db: AsyncSession, project, chapter: Chapter) -> dict:
    chapter_text = html.unescape(html_to_plain(chapter.content or "")).strip()
    if not chapter_text:
        return {"checked_entries": 0, "issues": []}

    events = await timeline(db, project.id)
    entries = [
        e for e in await relevant_entries(db, project.id, chapter_text[:2000], chapter_id=chapter.id, top_k=12)
        if e.kind != "event"
    ]
    if not entries and not events:
        return {"checked_entries": 0, "issues": []}

    facts = format_entries(entries, body_limit=800) if entries else "  (none relevant)"
    prompt = f"""You are a meticulous continuity editor for the book "{project.title}".

ESTABLISHED BOOK FACTS (the author's notes — treat these as correct):
{facts}

{format_timeline(events) if events else ''}

CHAPTER {chapter.chapter_number}: {chapter.title}
{chapter_text[:MAX_CHAPTER_CHARS]}

List every place where the chapter CONTRADICTS the established facts (names, ages, dates,
places, relationships, definitions, timeline, claims). Do not report style issues, omissions,
or things the facts simply don't mention.

Return ONLY a JSON array (empty if there are no contradictions):
[{{"entry": "title of the fact it contradicts", "quote": "exact sentence copied from the chapter", "issue": "what conflicts and how"}}]"""

    result = await get_llm_client().complete(messages=[{"role": "user", "content": prompt}], max_tokens=1200)
    return {"checked_entries": len(entries) + len(events), "issues": parse_issues(result.text, chapter_text)}
