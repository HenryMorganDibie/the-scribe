"""Regression tests for signup email casing, companion-chat quota/history and export headers."""
from types import SimpleNamespace

import pytest
from fastapi.responses import Response
from sqlalchemy.dialects import postgresql

from app.api.routes import auth, export, projects
from app.services.ai import companion_chat


# ── Signup email normalization ──────────────────────────────────────

def test_signup_lowercases_email():
    body = auth.SignupRequest(email="  John.Doe@Example.COM ", password="a" * 15, full_name="John")
    assert body.email == "john.doe@example.com"


class CapturingSession:
    def __init__(self, user=None):
        self.user = user
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: self.user))


@pytest.mark.asyncio
async def test_email_lookup_is_case_insensitive():
    db = CapturingSession(user="existing")
    assert await auth._find_user_by_email(db, " John@Example.com ") == "existing"

    compiled = db.statements[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    sql = str(compiled).lower()
    assert "lower(users.email) = 'john@example.com'" in sql


# ── Companion chat quota placement ──────────────────────────────────

@pytest.fixture
def quota_calls(monkeypatch):
    calls = []

    async def fake_quota(_db, user_id, action, _limit):
        calls.append((user_id, action))

    async def fake_owned_project(*_args, **_kwargs):
        return SimpleNamespace(id="p1")

    async def fake_history(*_args, **_kwargs):
        return []

    async def fake_save(*_args, **_kwargs):
        return None

    monkeypatch.setattr(projects, "consume_user_quota", fake_quota)
    monkeypatch.setattr(projects, "get_owned_project", fake_owned_project)
    monkeypatch.setattr(projects, "get_history", fake_history)
    monkeypatch.setattr(projects, "save_message", fake_save)
    return calls


@pytest.mark.asyncio
async def test_companion_history_does_not_consume_ai_quota(quota_calls):
    user = SimpleNamespace(id="u1")
    assert await projects.companion_chat_history("p1", user, db=object()) == []
    assert quota_calls == []


@pytest.mark.asyncio
async def test_companion_chat_consumes_ai_quota_before_streaming(quota_calls):
    user = SimpleNamespace(id="u1")
    body = projects.CompanionChatRequest(message="Have I covered grace?")
    await projects.companion_chat("p1", body, user, db=object())
    assert quota_calls == [("u1", "ai_request")]


# ── Companion chat history window ───────────────────────────────────

@pytest.mark.asyncio
async def test_history_returns_most_recent_messages_oldest_first():
    newest_first = ["m3", "m2", "m1"]
    captured = []

    class Session:
        async def execute(self, statement):
            captured.append(statement)
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: list(newest_first)))

    messages = await companion_chat.get_history("p1", Session(), limit=3)

    assert messages == ["m1", "m2", "m3"]
    sql = str(captured[0].compile(dialect=postgresql.dialect())).lower()
    assert "order by companion_chat_messages.created_at desc" in sql
    assert "limit" in sql


# ── Export Content-Disposition ──────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "faith’s-reward—part-1-manuscript.docx",
    "благодать-manuscript.pdf",
    'evil"\r\nset-cookie: x=1.docx',
])
def test_content_disposition_is_latin1_safe(filename):
    header = export._content_disposition(filename)

    # Must not raise: this is what Starlette does when sending headers.
    Response(content=b"", headers={"Content-Disposition": header})
    header.encode("latin-1")
    assert "\r" not in header and "\n" not in header
    assert header.startswith('attachment; filename="')
    assert "filename*=UTF-8''" in header


def test_content_disposition_keeps_ascii_titles_readable():
    header = export._content_disposition("my-book-manuscript.docx")
    assert header.startswith('attachment; filename="my-book-manuscript.docx";')
