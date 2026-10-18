"""
Book bible + per-book source library: the retrievable knowledge of one book.

Entries (characters, places, terms, sources, notes, research) are embedded
into document_embeddings with doc_type='book_entry' and project_id set, the
same way chapters are indexed for Companion Chat. Indexing runs inline when
an entry is saved — it's one small local embedding, and doing it in-request
means it can't be lost the way in-process background tasks can.

`book_context()` assembles what a generation prompt should know about the
book: the bible entries relevant to the query, entries attached to the
current chapter, and passages from the book's linked sources.
"""
from typing import Optional

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BookEntry, DocumentEmbedding, Project
from app.services.voice.embeddings import embedding_service

logger = structlog.get_logger()

ENTRY_KINDS = ("character", "place", "term", "event", "source", "note", "research")
KIND_LABELS = {
    "character": "Character",
    "place": "Place",
    "term": "Term",
    "event": "Timeline event",
    "source": "Source",
    "note": "Note",
    "research": "Research",
}


def _heading(entry: BookEntry) -> str:
    when = f" ({entry.when_label})" if getattr(entry, "when_label", None) else ""
    return f"{entry.title}{when}"


def _entry_text(entry: BookEntry) -> str:
    return f"{KIND_LABELS.get(entry.kind, entry.kind)}: {_heading(entry)}\n{entry.body or ''}".strip()


async def index_entry(db: AsyncSession, entry: BookEntry) -> None:
    """(Re-)embed one entry. Failures are logged, never raised — the entry is still saved."""
    try:
        await db.execute(delete(DocumentEmbedding).where(
            DocumentEmbedding.doc_type == "book_entry",
            DocumentEmbedding.source_id == entry.id,
        ))
        chunks = embedding_service.chunk_text(_entry_text(entry), chunk_size=300, overlap=40)
        vectors = await embedding_service.embed_batch(chunks)
        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            db.add(DocumentEmbedding(
                user_id=entry.user_id, doc_type="book_entry", source_id=entry.id,
                project_id=entry.project_id, chunk_index=i, content=chunk, embedding=vector,
            ))
    except Exception:
        logger.exception("book_entry_index_failed", entry_id=entry.id)


async def remove_entry_index(db: AsyncSession, entry_id: str) -> None:
    await db.execute(delete(DocumentEmbedding).where(
        DocumentEmbedding.doc_type == "book_entry",
        DocumentEmbedding.source_id == entry_id,
    ))


async def relevant_entries(
    db: AsyncSession, project_id: str, query: str, *, chapter_id: Optional[str] = None, top_k: int = 6,
) -> list[BookEntry]:
    """Entries attached to `chapter_id` first, then the most similar entries in the book."""
    entries: list[BookEntry] = []
    if chapter_id:
        attached = await db.execute(
            select(BookEntry).where(BookEntry.project_id == project_id, BookEntry.chapter_id == chapter_id)
            .order_by(BookEntry.updated_at.desc()).limit(top_k)
        )
        entries.extend(attached.scalars().all())

    if query.strip():
        query_vector = await embedding_service.embed(query)
        rows = (await db.execute(
            text("""
                SELECT source_id, MIN(embedding <=> :embedding) AS distance
                FROM document_embeddings
                WHERE project_id = :project_id AND doc_type = 'book_entry'
                GROUP BY source_id
                ORDER BY distance
                LIMIT :k
            """),
            {"embedding": str(query_vector), "project_id": project_id, "k": top_k},
        )).fetchall()
        ranked_ids = [row[0] for row in rows if row[0] not in {e.id for e in entries}]
        if ranked_ids:
            found = (await db.execute(
                select(BookEntry).where(BookEntry.id.in_(ranked_ids), BookEntry.project_id == project_id)
            )).scalars().all()
            by_id = {e.id: e for e in found}
            entries.extend(by_id[i] for i in ranked_ids if i in by_id)

    return entries


async def relevant_source_passages(db: AsyncSession, project: Project, query: str, *, top_k: int = 4) -> list[str]:
    """Most similar transcript chunks from the sources linked to this book."""
    source_ids = [s for s in (project.source_sermon_ids or []) if isinstance(s, str)]
    if not source_ids or not query.strip():
        return []
    query_vector = await embedding_service.embed(query)
    rows = (await db.execute(
        text("""
            SELECT content
            FROM document_embeddings
            WHERE user_id = :user_id AND doc_type = 'sermon' AND source_id = ANY(:source_ids)
            ORDER BY embedding <=> :embedding
            LIMIT :k
        """),
        {"embedding": str(query_vector), "user_id": project.user_id, "source_ids": source_ids, "k": top_k},
    )).fetchall()
    return [row[0] for row in rows]


def format_entries(entries: list[BookEntry], *, body_limit: int = 600) -> str:
    return "\n".join(
        f"  • [{KIND_LABELS.get(e.kind, e.kind)}] {_heading(e)}: {(e.body or '').strip()[:body_limit]}".rstrip(": ")
        for e in entries
    )


MAX_TIMELINE_EVENTS = 40


async def timeline(db: AsyncSession, project_id: str) -> list[BookEntry]:
    """The book's timeline events in story order (unordered events last, oldest first)."""
    result = await db.execute(
        select(BookEntry)
        .where(BookEntry.project_id == project_id, BookEntry.kind == "event")
        .order_by(BookEntry.timeline_order.asc().nulls_last(), BookEntry.created_at)
        .limit(MAX_TIMELINE_EVENTS)
    )
    return list(result.scalars().all())


def format_timeline(events: list[BookEntry], *, body_limit: int = 300) -> str:
    lines = [
        f"  {i}. {_heading(e)}" + (f" — {(e.body or '').strip()[:body_limit]}" if (e.body or "").strip() else "")
        for i, e in enumerate(events, start=1)
    ]
    return "TIMELINE (events in story order — never reorder or contradict them):\n" + "\n".join(lines)


async def book_context(
    db: AsyncSession, project: Project, query: str, *, chapter_id: Optional[str] = None,
) -> str:
    """Prompt section with this book's timeline, relevant bible entries and source passages ("" if none)."""
    events = await timeline(db, project.id)
    # Events are already listed in full, in order, under TIMELINE.
    entries = [e for e in await relevant_entries(db, project.id, query, chapter_id=chapter_id) if e.kind != "event"]
    passages = await relevant_source_passages(db, project, query)

    sections = []
    if events:
        sections.append(format_timeline(events))
    if entries:
        sections.append(
            "ESTABLISHED BOOK FACTS (the author's notes on this book — stay consistent with them, never contradict them):\n"
            + format_entries(entries)
        )
    if passages:
        sections.append(
            "FROM THIS BOOK'S SOURCE MATERIAL (the author's own words — draw on these ideas and stories):\n"
            + "\n---\n".join(p[:1200] for p in passages)
        )
    return "\n\n".join(sections)
