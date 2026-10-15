"""Chapter/project deletes against a real Postgres (pgvector) database.

These exercise the foreign keys and ORM cascade rules that unit tests with
fake sessions cannot. Skipped unless TEST_DATABASE_URL points at a
DISPOSABLE database — the module migrates it to head and writes test rows.

    docker run -d --rm --name scribe-test-pg -e POSTGRES_USER=scribe \\
      -e POSTGRES_PASSWORD=scribe -e POSTGRES_DB=scribe_test -p 5435:5432 ankane/pgvector
    TEST_DATABASE_URL=postgresql://scribe:scribe@localhost:5435/scribe_test pytest tests/test_delete_integration.py
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.routes import projects
from app.core.config import normalize_db_url
from app.models import (
    Chapter, CompanionChatMessage, DocumentEmbedding, GenerationLog, Project, User, VoiceVersion,
)

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def migrated_database():
    # Run the real migrations so this also verifies 0006 applies cleanly.
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


async def _seed(db) -> SimpleNamespace:
    """A project with one chapter that has every kind of dependent row."""
    user = User(email=f"{uuid.uuid4().hex}@example.com", hashed_password="x", full_name="Author")
    db.add(user)
    await db.flush()
    project = Project(user_id=user.id, title="Grace Abounding")
    db.add(project)
    await db.flush()
    chapter = Chapter(project_id=project.id, user_id=user.id, title="Called", chapter_number=1, position=0)
    db.add(chapter)
    await db.flush()
    log = GenerationLog(user_id=user.id, chapter_id=chapter.id, action="generate_chapter", model="test")
    version = VoiceVersion(user_id=user.id, version_number=1, snapshot={}, trigger="edit_accepted", chapter_id=chapter.id)
    db.add_all([
        log,
        version,
        DocumentEmbedding(
            user_id=user.id, doc_type="chapter", source_id=chapter.id, project_id=project.id,
            content="chunk", embedding=[0.0] * 384,
        ),
        CompanionChatMessage(project_id=project.id, user_id=user.id, role="user", content="hi"),
    ])
    await db.commit()
    return SimpleNamespace(user=user, project=project, chapter=chapter, log=log, version=version)


async def _count(db, model, *conditions) -> int:
    return (await db.execute(select(func.count()).select_from(model).where(*conditions))).scalar_one()


async def _chapter_ref(db, model, row_id):
    """(row exists, its chapter_id) — read fresh from the database."""
    row = (await db.execute(select(model.chapter_id).where(model.id == row_id))).first()
    return (row is not None, row[0] if row else None)


async def test_delete_chapter_with_ai_history(db):
    s = await _seed(db)

    await projects.delete_chapter(s.project.id, s.chapter.id, current_user=s.user, db=db)

    assert await _count(db, Chapter, Chapter.id == s.chapter.id) == 0
    assert await _count(db, DocumentEmbedding, DocumentEmbedding.source_id == s.chapter.id) == 0
    # History rows survive, detached from the deleted chapter.
    assert await _chapter_ref(db, GenerationLog, s.log.id) == (True, None)
    assert await _chapter_ref(db, VoiceVersion, s.version.id) == (True, None)


async def test_delete_project_with_chapters(db):
    s = await _seed(db)

    await projects.delete_project(s.project.id, current_user=s.user, db=db)

    assert await _count(db, Project, Project.id == s.project.id) == 0
    assert await _count(db, Chapter, Chapter.project_id == s.project.id) == 0
    assert await _count(db, DocumentEmbedding, DocumentEmbedding.project_id == s.project.id) == 0
    assert await _count(db, CompanionChatMessage, CompanionChatMessage.project_id == s.project.id) == 0
    assert await _chapter_ref(db, GenerationLog, s.log.id) == (True, None)
