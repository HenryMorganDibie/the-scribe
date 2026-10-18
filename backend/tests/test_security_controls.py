"""Focused regression coverage for production security controls."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request, Response
from pydantic import ValidationError

from app.api.routes.auth import SignupRequest
from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_browser_session,
    hash_session_secret,
    require_csrf,
    set_browser_session_cookie,
)


def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    return Request({"type": "http", "method": "POST", "headers": headers})


def test_signup_rejects_short_and_bcrypt_overlong_passwords():
    with pytest.raises(ValidationError):
        SignupRequest(email="author@example.com", password="too-short", full_name="Author")
    with pytest.raises(ValidationError):
        SignupRequest(email="author@example.com", password="a" * 73, full_name="Author")


def _cookie_request(session_token: str, csrf: str | None) -> Request:
    from app.core.config import settings

    headers = [(b"cookie", f"{settings.SESSION_COOKIE_NAME}={session_token}".encode())]
    if csrf is not None:
        headers.append((b"x-csrf-token", csrf.encode()))
    return _request(headers)


def test_csrf_requires_the_token_derived_from_this_session():
    from app.core.security import csrf_token_for

    good = csrf_token_for("session-a")
    require_csrf(_cookie_request("session-a", good))
    for request in (
        _cookie_request("session-a", "wrong"),
        _cookie_request("session-a", None),
        _cookie_request("session-b", good),          # another session's token
        _request([(b"x-csrf-token", good.encode())]),  # no session cookie at all
    ):
        with pytest.raises(HTTPException) as exc_info:
            require_csrf(request)
        assert exc_info.value.status_code == 403


async def test_every_tab_gets_the_same_csrf_token_from_me():
    """Reloading one tab must not invalidate the token another tab holds."""
    from app.api.routes import auth
    from app.core.security import csrf_token_for

    class Session:
        last_seen_at = None

    class FakeDB:
        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: "general")

        async def commit(self):
            return None

    async def fake_session(*_args):
        return Session()

    original = auth.get_browser_session
    auth.get_browser_session = fake_session
    try:
        user = SimpleNamespace(id="u1", email="a@x.com", full_name="A", onboarded=True, avatar_url=None)
        first = await auth.me(_cookie_request("session-a", None), current_user=user, db=FakeDB())
        second = await auth.me(_cookie_request("session-a", None), current_user=user, db=FakeDB())
    finally:
        auth.get_browser_session = original

    assert first["csrf_token"] == second["csrf_token"] == csrf_token_for("session-a")
    require_csrf(_cookie_request("session-a", first["csrf_token"]))


def test_session_cookie_is_http_only():
    response = Response()
    set_browser_session_cookie(response, "opaque-value")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


@pytest.mark.asyncio
async def test_browser_session_stores_hashes_not_raw_tokens():
    class FakeSession:
        def __init__(self):
            self.added = []

        def add(self, value):
            self.added.append(value)

        async def commit(self):
            return None

    db = FakeSession()
    token, csrf = await create_browser_session(db, "user-1")
    stored = db.added[0]
    assert stored.token_hash == hash_session_secret(token)
    assert stored.csrf_token_hash == hash_session_secret(csrf)
    assert token not in stored.token_hash


def test_new_bearer_tokens_are_versioned():
    from jose import jwt
    from app.core.config import settings

    token = create_access_token({"sub": "user-1"})
    assert jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["v"] == 2


def test_production_rejects_insecure_cookie_configuration():
    config = Settings(ENVIRONMENT="production", SECRET_KEY="a" * 32, SESSION_COOKIE_SECURE=False)
    with pytest.raises(RuntimeError):
        config.validate_for_startup()
