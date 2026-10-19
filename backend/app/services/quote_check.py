"""
Quote verification for non-fiction: is each quotation in a chapter really in
the book's sources?

Sources are the book's linked source transcripts plus its book-bible
"source" and "research" entries. Each quoted passage (six words or more, so
scare quotes and short phrases are skipped) is matched word by word:

  verified   — appears verbatim (ignoring case, punctuation and spacing)
  close      — at least CLOSE_MATCH of its words match a source passage in order;
               the source's actual wording is returned so the author can fix it
  not_found  — no source contains it

No AI is involved, so the check is free and can't hallucinate a source.
"""
import html
import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BookEntry, Sermon
from app.services.export.docx_export import html_to_plain

MIN_QUOTE_WORDS = 6
CLOSE_MATCH = 0.8
MAX_QUOTES = 30

_QUOTE = re.compile(r'"([^"\n]{10,1500})"|“([^”]{10,1500})”')
_TOKEN = re.compile(r"[^\w']+")


def _norm(word: str) -> str:
    return _TOKEN.sub("", word.lower().replace("’", "'"))


def extract_quotes(text: str) -> list[str]:
    quotes, seen = [], set()
    for match in _QUOTE.finditer(text):
        quote = (match.group(1) or match.group(2)).strip()
        key = " ".join(_norm(w) for w in quote.split())
        if len(quote.split()) >= MIN_QUOTE_WORDS and key not in seen:
            seen.add(key)
            quotes.append(quote)
    return quotes[:MAX_QUOTES]


def _tokens(text: str) -> tuple[list[str], list[str]]:
    original = text.split()
    normalized = [_norm(w) for w in original]
    keep = [i for i, w in enumerate(normalized) if w]
    return [original[i] for i in keep], [normalized[i] for i in keep]


def match_quote(quote: str, sources: list[tuple[str, str]]) -> dict:
    """Best match for one quote across (title, text) sources."""
    _, q = _tokens(quote)
    best = {"quote": quote, "status": "not_found", "source_title": None, "source_excerpt": None, "score": 0.0}
    if not q:
        return best

    joined_q = " ".join(q)
    for title, text in sources:
        original, s = _tokens(text)
        if not s:
            continue
        if f" {joined_q} " in f" {' '.join(s)} ":
            return {**best, "status": "verified", "source_title": title, "score": 1.0}

        blocks = [b for b in SequenceMatcher(None, q, s, autojunk=False).get_matching_blocks() if b.size]
        score = sum(b.size for b in blocks) / len(q)
        if score > best["score"] and blocks:
            start = max(blocks[0].b - 3, 0)
            end = min(blocks[-1].b + blocks[-1].size + 3, len(original))
            # Only trust an in-order match that stays local — not words scattered across the source.
            if end - start <= len(q) * 2 + 6:
                best = {**best, "source_title": title, "score": score,
                        "source_excerpt": " ".join(original[start:end])}

    if best["score"] >= CLOSE_MATCH:
        best["status"] = "close"
    else:
        best.update(source_title=None, source_excerpt=None)
    return best


async def book_sources(db: AsyncSession, project) -> list[tuple[str, str]]:
    sources: list[tuple[str, str]] = []
    source_ids = [s for s in (project.source_sermon_ids or []) if isinstance(s, str)]
    if source_ids:
        sermons = (await db.execute(
            select(Sermon).where(Sermon.id.in_(source_ids), Sermon.user_id == project.user_id)
        )).scalars().all()
        sources += [(s.title, s.transcript or "") for s in sermons if s.transcript]
    entries = (await db.execute(
        select(BookEntry).where(BookEntry.project_id == project.id, BookEntry.kind.in_(("source", "research")))
    )).scalars().all()
    sources += [(e.title, e.body or "") for e in entries if (e.body or "").strip()]
    return sources


async def verify_chapter_quotes(db: AsyncSession, project, chapter) -> dict:
    text = html.unescape(html_to_plain(chapter.content or ""))
    quotes = extract_quotes(text)
    sources = await book_sources(db, project)
    results = [match_quote(q, sources) for q in quotes] if sources else [
        {"quote": q, "status": "not_found", "source_title": None, "source_excerpt": None, "score": 0.0} for q in quotes
    ]
    for r in results:
        r["score"] = round(r["score"], 2)
    return {"checked_sources": len(sources), "quotes": results}
