"""Book workspace against a real Postgres (pgvector): draft history, book bible, linked sources.

Skipped unless TEST_DATABASE_URL points at a DISPOSABLE database — see
tests/test_delete_integration.py for how to start one.
"""
import hashlib
import math
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.routes import book_bible as bible_routes
from app.api.routes import projects
from app.core.config import normalize_db_url
from app.models import BookEntry, Chapter, ChapterVersion, DocumentEmbedding, Project, Sermon, User
from app.services import book_bible, chapter_versions
from app.services.voice import embeddings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _fake_vector(text: str) -> list[float]:
    """Deterministic bag-of-words vector: texts sharing words are similar."""
    vec = [0.0] * 384
    for word in text.lower().split():
        vec[int(hashlib.md5(word.strip(".,:;!?").encode()).hexdigest(), 16) % 384] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@pytest.fixture(autouse=True)
def fake_embeddings(monkeypatch):
    async def embed_batch(texts):
        return [_fake_vector(t) for t in texts]

    async def embed(text):
        return _fake_vector(text)

    monkeypatch.setattr(embeddings.embedding_service, "embed_batch", embed_batch)
    monkeypatch.setattr(embeddings.embedding_service, "embed", embed)


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR, env=env, check=True, capture_output=True,
    )


@pytest.fixture
async def db():
    engine = create_async_engine(
        normalize_db_url(TEST_DATABASE_URL),
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


async def _seed(db, content="<p>First draft.</p>"):
    user = User(email=f"{uuid.uuid4().hex}@example.com", hashed_password="x", full_name="Author")
    db.add(user)
    await db.flush()
    project = Project(user_id=user.id, title="The Quiet Hours")
    db.add(project)
    await db.flush()
    chapter = Chapter(project_id=project.id, user_id=user.id, title="Dawn", chapter_number=1, position=0,
                      content=content, word_count=2)
    db.add(chapter)
    await db.commit()
    return SimpleNamespace(user=user, project=project, chapter=chapter)


async def _versions(db, chapter_id):
    return (await db.execute(
        select(ChapterVersion.reason, ChapterVersion.content)
        .where(ChapterVersion.chapter_id == chapter_id).order_by(ChapterVersion.created_at)
    )).all()


async def _save(db, s, content, *, explicit=False):
    await projects.update_chapter(
        s.project.id, s.chapter.id,
        projects.ChapterUpdate(content=content, trigger_indexing=explicit),
        BackgroundTasks(), current_user=s.user, db=db,
    )


# ── Draft history ───────────────────────────────────────────────────

async def test_autosaves_are_throttled_but_explicit_saves_always_keep_a_copy(db):
    s = await _seed(db)

    await _save(db, s, "<p>Second.</p>")   # keeps "First draft"
    await _save(db, s, "<p>Third.</p>")    # within 10 minutes — skipped
    await _save(db, s, "<p>Fourth.</p>", explicit=True)  # explicit — keeps "Third"

    assert await _versions(db, s.chapter.id) == [
        ("autosave", "<p>First draft.</p>"),
        ("manual", "<p>Third.</p>"),
    ]


async def test_autosave_snapshots_again_after_the_interval(db, monkeypatch):
    s = await _seed(db)
    await _save(db, s, "<p>Second.</p>")
    later = datetime.utcnow() + chapter_versions.AUTOSAVE_INTERVAL + timedelta(seconds=1)
    monkeypatch.setattr(chapter_versions, "datetime", SimpleNamespace(utcnow=lambda: later))

    await _save(db, s, "<p>Third.</p>")

    assert [r for r, _ in await _versions(db, s.chapter.id)] == ["autosave", "autosave"]


async def test_restore_replaces_content_and_keeps_the_replaced_draft(db):
    s = await _seed(db)
    await _save(db, s, "<p>Rewritten badly.</p>")
    first = (await db.execute(select(ChapterVersion).where(ChapterVersion.chapter_id == s.chapter.id))).scalar_one()

    result = await projects.restore_chapter_version(
        s.project.id, s.chapter.id, first.id, BackgroundTasks(), current_user=s.user, db=db,
    )

    assert result["content"] == "<p>First draft.</p>"
    assert (await db.execute(select(Chapter.content).where(Chapter.id == s.chapter.id))).scalar_one() == "<p>First draft.</p>"
    assert ("before_restore", "<p>Rewritten badly.</p>") in await _versions(db, s.chapter.id)


async def test_versions_are_pruned_to_the_newest(db, monkeypatch):
    monkeypatch.setattr(chapter_versions, "MAX_VERSIONS", 3)
    s = await _seed(db)
    for i in range(6):
        await _save(db, s, f"<p>Draft {i}.</p>", explicit=True)

    contents = [c for _, c in await _versions(db, s.chapter.id)]
    assert contents == ["<p>Draft 2.</p>", "<p>Draft 3.</p>", "<p>Draft 4.</p>"]


async def test_versions_are_private_to_their_chapter(db):
    a = await _seed(db)
    b = await _seed(db)
    await _save(db, a, "<p>Changed.</p>")
    version_id = (await db.execute(select(ChapterVersion.id).where(ChapterVersion.chapter_id == a.chapter.id))).scalar_one()

    with pytest.raises(Exception) as exc_info:
        await projects.get_chapter_version(b.project.id, b.chapter.id, version_id, current_user=b.user, db=db)
    assert getattr(exc_info.value, "status_code", None) == 404


# ── Book bible ──────────────────────────────────────────────────────

async def _create(db, s, kind, title, body="", chapter_id=None):
    return await bible_routes.create_entry(
        s.project.id, bible_routes.EntryCreate(kind=kind, title=title, body=body, chapter_id=chapter_id),
        current_user=s.user, db=db,
    )


async def test_entries_are_indexed_retrieved_and_cleaned_up(db):
    s = await _seed(db)
    ada = await _create(db, s, "character", "Ada Obi", "Lighthouse keeper who fears the sea storms")
    await _create(db, s, "place", "Harbour Market", "Busy fish market at dawn")
    note = await _create(db, s, "note", "Open quietly", "Start chapter one before sunrise", chapter_id=s.chapter.id)

    indexed = (await db.execute(
        select(func.count()).select_from(DocumentEmbedding).where(DocumentEmbedding.source_id == ada["id"])
    )).scalar_one()
    assert indexed >= 1

    found = await book_bible.relevant_entries(db, s.project.id, "the keeper and the storms", chapter_id=s.chapter.id)
    titles = [e.title for e in found]
    assert titles[0] == "Open quietly"  # attached to this chapter, always first
    assert titles.index("Ada Obi") < titles.index("Harbour Market")

    await bible_routes.delete_entry(s.project.id, ada["id"], current_user=s.user, db=db)
    remaining = (await db.execute(
        select(func.count()).select_from(DocumentEmbedding).where(DocumentEmbedding.source_id == ada["id"])
    )).scalar_one()
    assert remaining == 0

    # Deleting the chapter detaches its notes instead of deleting them.
    await projects.delete_chapter(s.project.id, s.chapter.id, current_user=s.user, db=db)
    detached = (await db.execute(select(BookEntry.chapter_id).where(BookEntry.id == note["id"]))).scalar_one()
    assert detached is None


async def test_entries_cannot_attach_to_another_books_chapter(db):
    a = await _seed(db)
    b = await _seed(db)
    with pytest.raises(Exception) as exc_info:
        await _create(db, a, "note", "Sneaky", chapter_id=b.chapter.id)
    assert getattr(exc_info.value, "status_code", None) == 404


async def test_book_context_includes_entries_and_linked_source_passages(db):
    s = await _seed(db)
    await _create(db, s, "term", "The Quiet Hours", "The two hours before the city wakes")
    sermon = Sermon(user_id=s.user.id, title="Talk on mornings", source_type="text", status="complete",
                    transcript="Mornings are where deep work happens before the city wakes.")
    db.add(sermon)
    await db.flush()
    db.add(DocumentEmbedding(
        user_id=s.user.id, doc_type="sermon", source_id=sermon.id, chunk_index=0,
        content=sermon.transcript, embedding=_fake_vector(sermon.transcript),
    ))
    await db.commit()

    unlinked = await book_bible.book_context(db, s.project, "before the city wakes")
    assert "The Quiet Hours" in unlinked and "deep work" not in unlinked  # source not linked yet

    s.project.source_sermon_ids = [sermon.id]
    linked = await book_bible.book_context(db, s.project, "before the city wakes")
    assert "ESTABLISHED BOOK FACTS" in linked
    assert "FROM THIS BOOK'S SOURCE MATERIAL" in linked and "deep work" in linked
