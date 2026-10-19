"""Regression tests for Google account sign-in and provisioning."""
from types import SimpleNamespace

import pytest
import jwt

from app.api.routes import auth
from app.core.config import settings


class FakeResult:
    def __init__(self, scalar=None):
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(first=lambda: self.scalar)


class FakeSession:
    def __init__(self, existing_user=None):
        self.existing_user = existing_user
        self.added = []
        self.commits = 0

    async def execute(self, _statement):
        return FakeResult(self.existing_user)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.added[0].id = "new-google-user"

    async def commit(self):
        self.commits += 1

    async def refresh(self, _value):
        return None


@pytest.mark.asyncio
async def test_google_sign_in_provisions_user_and_voice_profile(monkeypatch):
    async def verified_credential(_credential):
        return {
            "email": "Author@Example.com",
            "email_verified": True,
            "name": "Author Example",
        }

    monkeypatch.setattr(auth, "verify_google_credential", verified_credential)
    db = FakeSession()

    response = await auth.google_sign_in(
        auth.GoogleSignInRequest(credential="google-id-token"),
        db,
    )

    assert response.user == {
        "id": "new-google-user",
        "email": "author@example.com",
        "full_name": "Author Example",
        "onboarded": False,
        "pack": "general",
    }
    assert len(db.added) == 2
    assert db.added[1].user_id == "new-google-user"
    assert db.commits == 1
    assert jwt.decode(response.access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])["sub"] == "new-google-user"


@pytest.mark.asyncio
async def test_google_sign_in_reuses_existing_account(monkeypatch):
    async def verified_credential(_credential):
        return {"email": "author@example.com", "email_verified": True}

    monkeypatch.setattr(auth, "verify_google_credential", verified_credential)
    existing_user = SimpleNamespace(
        id="existing-user",
        email="author@example.com",
        full_name="Existing Author",
        onboarded=True,
    )
    db = FakeSession(existing_user)

    response = await auth.google_sign_in(
        auth.GoogleSignInRequest(credential="google-id-token"),
        db,
    )

    assert response.user["id"] == "existing-user"
    assert db.added == []
    assert db.commits == 0
