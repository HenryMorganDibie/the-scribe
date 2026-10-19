"""Regression coverage for Google authentication configuration."""
import pytest
from fastapi import HTTPException

from app.api.routes import auth
from app.core.config import settings


@pytest.mark.asyncio
async def test_google_sign_in_reports_missing_server_configuration(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")

    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_google_credential("google-id-token")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Google sign-in is not configured"
