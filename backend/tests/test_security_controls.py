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


def test_csrf_requires_matching_secret():
    session = SimpleNamespace(csrf_token_hash=hash_session_secret("correct"))
    require_csrf(_request([(b"x-csrf-token", b"correct")]), session)
    with pytest.raises(HTTPException) as exc_info:
        require_csrf(_request([(b"x-csrf-token", b"wrong")]), session)
    assert exc_info.value.status_code == 403


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
