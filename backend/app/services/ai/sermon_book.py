"""Build a manuscript blueprint from an author's selected sermons."""
import json
from typing import Any

from app.services.ai.json_utils import strip_json_fences
from app.services.ai.llm_client import get_llm_client


def _clean_chapters(raw: Any, target_chapters: int) -> list[dict]:
    """Return a safe, compact chapter plan from imperfect model JSON."""
    if not isinstance(raw, list):
        return []

    chapters = []
    for item in raw[:target_chapters]:
        if not isinstance(item, dict) or not str(item.get("title", "")).strip():
            continue
        points = item.get("key_points", [])
        if not isinstance(points, list):
            points = []
        scriptures = item.get("anchor_scriptures", [])
        if not isinstance(scriptures, list):
            scriptures = []
        chapters.append({
            "title": str(item["title"]).strip()[:160],
            "intent": str(item.get("intent", "")).strip()[:600],
            "key_points": [str(point).strip()[:280] for point in points if str(point).strip()][:5],
            "anchor_scriptures": [str(ref).strip()[:80] for ref in scriptures if str(ref).strip()][:4],
        })
    return chapters


async def build_sermon_book_plan(
    *,
    title: str,
    target_reader: str,
    target_chapters: int,
    theological_lens: str | None,
    preferred_translation: str | None,
    guardrails: list[str] | None,
    sermons: list,
) -> dict:
    """Ask the active model for a grounded book outline, then validate it."""
    source_material = "\n\n".join(
        f"SOURCE SERMON: {sermon.title}\n{(sermon.transcript or '')[:3500]}"
        for sermon in sermons
    )[:18000]
    rules = "\n".join(f"- {rule}" for rule in (guardrails or []) if rule.strip()) or "- Remain faithful to the author's stated theological lens."

    prompt = f"""You are a Christian book-development editor. Create a practical manuscript blueprint from ONLY the author's selected sermons.

BOOK TITLE: {title}
TARGET READER: {target_reader or 'General Christian reader'}
TARGET CHAPTER COUNT: {target_chapters}
THEOLOGICAL LENS: {theological_lens or 'Not specified'}
PREFERRED BIBLE TRANSLATION: {preferred_translation or 'NKJV'}
THEOLOGICAL GUARDRAILS:
{rules}

SELECTED SERMON SOURCES:
{source_material}

Do not invent biographical claims, testimonies, or scripture references. Build a coherent progression from the supplied messages. Return ONLY valid JSON in this shape:
{{
  "theme": "one-sentence central promise of the book",
  "chapters": [
    {{"title": "chapter title", "intent": "what this chapter accomplishes", "key_points": ["point"], "anchor_scriptures": ["Reference only when explicitly supported by source material"]}}
  ]
}}
"""

    llm = get_llm_client()
    result = await llm.complete(messages=[{"role": "user", "content": prompt}], max_tokens=1800)
    try:
        parsed = json.loads(strip_json_fences(result.text))
    except (json.JSONDecodeError, TypeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    chapters = _clean_chapters(parsed.get("chapters"), target_chapters)
    if not chapters:
        raise ValueError("The book blueprint could not be created. Please try again.")
    return {"theme": str(parsed.get("theme", "")).strip()[:1000], "chapters": chapters}
