"""Regression tests for tenant ownership enforcement on project resources."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.ownership import get_owned_chapter
from app.api.routes.generate import (
    ChatRequest,
    ContinueRequest,
    GenerateChapterRequest,
    ScriptureSuggestRequest,
    VoiceCheckRequest,
    WeaveStoryRequest,
    continue_writing,
    generate_chapter,
    scripture_suggest,
    scribe_chat,
    voice_check,
    weave_story,
)
from app.api.routes.projects import (
    ChapterCreate,
    ReorderRequest,
    create_chapter,
    reorder_chapters,
)


class FakeResult:
    def __init__(self, *, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, *results):
        self.results = list(results)
        self.statements = []
        self.added = []
        self.commits = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def refresh(self, value):
        return None


USER = SimpleNamespace(id="user-a")


@pytest.mark.asyncio
async def test_create_chapter_rejects_foreign_project_before_writing():
    db = FakeSession(FakeResult(scalar=None))

    with pytest.raises(HTTPException) as exc:
        await create_chapter(
            "foreign-project",
            ChapterCreate(title="Injected chapter", chapter_number=1),
            USER,
            db,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found"
    assert db.added == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_reorder_rejects_foreign_project_before_writing():
    db = FakeSession(FakeResult(scalar=None))

    with pytest.raises(HTTPException) as exc:
        await reorder_chapters(
            "foreign-project",
            ReorderRequest(order=["foreign-chapter"]),
            USER,
            db,
        )

    assert exc.value.status_code == 404
    assert db.commits == 0


@pytest.mark.asyncio
async def test_reorder_rejects_chapter_ids_outside_owned_project():
    project = SimpleNamespace(id="project-a", user_id=USER.id)
    chapter = SimpleNamespace(id="chapter-a", position=0)
    db = FakeSession(
        FakeResult(scalar=project),
        FakeResult(rows=[chapter]),
    )

    with pytest.raises(HTTPException) as exc:
        await reorder_chapters(
            project.id,
            ReorderRequest(order=[chapter.id, "foreign-chapter"]),
            USER,
            db,
        )

    assert exc.value.status_code == 400
    assert db.commits == 0
    assert chapter.position == 0


@pytest.mark.asyncio
async def test_owned_chapter_lookup_scopes_id_user_and_project():
    chapter = SimpleNamespace(id="chapter-a", user_id=USER.id, project_id="project-a")
    db = FakeSession(FakeResult(scalar=chapter))

    found = await get_owned_chapter(
        chapter.id,
        USER.id,
        db,
        project_id=chapter.project_id,
    )

    assert found is chapter
    sql = str(db.statements[0])
    assert "chapters.id" in sql
    assert "chapters.user_id" in sql
    assert "chapters.project_id" in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "body"),
    [
        (generate_chapter, GenerateChapterRequest(chapter_id="foreign-chapter")),
        (
            continue_writing,
            ContinueRequest(chapter_id="foreign-chapter", cursor_text="text"),
        ),
        (
            weave_story,
            WeaveStoryRequest(
                chapter_id="foreign-chapter",
                testimony_id="testimony-a",
                cursor_text="text",
            ),
        ),
        (
            voice_check,
            VoiceCheckRequest(chapter_id="foreign-chapter", text="text"),
        ),
        (
            scripture_suggest,
            ScriptureSuggestRequest(chapter_id="foreign-chapter", context="text"),
        ),
        (
            scribe_chat,
            ChatRequest(chapter_id="foreign-chapter", message="help"),
        ),
    ],
)
async def test_generation_endpoints_reject_foreign_chapter_before_ai(endpoint, body):
    db = FakeSession(FakeResult(scalar=None))

    with pytest.raises(HTTPException) as exc:
        await endpoint(body, USER, db)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Chapter not found"
    assert len(db.statements) == 1
    assert db.added == []
    assert db.commits == 0
