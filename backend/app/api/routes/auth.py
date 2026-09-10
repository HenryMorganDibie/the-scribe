import asyncio
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    clear_browser_session_cookie,
    create_access_token,
    create_browser_session,
    get_browser_session,
    get_current_user,
    hash_password,
    hash_session_secret,
    set_browser_session_cookie,
    verify_password,
)
from app.db.session import get_db
from app.models import User, VoiceProfile
from app.services.security.rate_limits import enforce_auth_limit

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=15, max_length=64)
    full_name: str = Field(min_length=1, max_length=120)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password is too long")
        return value


class TokenResponse(BaseModel):
    # Temporary API-client compatibility only. The web client uses the secure
    # HttpOnly cookie and never persists this short-lived bearer token.
    access_token: str
    token_type: str = "bearer"
    csrf_token: str
    user: dict


class GoogleSignInRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=12_000)


async def _login_response(user: User, db: AsyncSession, response: Response | None) -> TokenResponse:
    # Keeping this branch also makes route functions easy to exercise directly
    # in unit tests; real HTTP requests always receive FastAPI's Response.
    if response is not None:
        session_token, csrf_token = await create_browser_session(db, user.id)
        set_browser_session_cookie(response, session_token)
    else:
        csrf_token = secrets.token_urlsafe(32)
    return TokenResponse(
        access_token=create_access_token({"sub": user.id}),
        csrf_token=csrf_token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name, "onboarded": user.onboarded},
    )


async def verify_google_credential(credential: str) -> dict:
    """Validate a Google Identity Services ID token for this application."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")

    def verify() -> dict:
        from google.auth.transport import requests
        from google.oauth2 import id_token

        return id_token.verify_oauth2_token(credential, requests.Request(), settings.GOOGLE_CLIENT_ID)

    try:
        claims = await asyncio.to_thread(verify)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Google credential") from exc

    email = claims.get("email")
    if not email or claims.get("email_verified") not in (True, "true"):
        raise HTTPException(status_code=401, detail="Google account email is not verified")
    return claims


@router.post("/signup", response_model=TokenResponse)
async def signup(
    body: SignupRequest,
    request: Request = None,
    response: Response = None,
    db: AsyncSession = Depends(get_db),
):
    if request is not None:
        await enforce_auth_limit(
            db, request, "signup", subject=body.email,
            limit=settings.SIGNUP_RATE_LIMIT_ATTEMPTS,
            window_minutes=settings.SIGNUP_RATE_LIMIT_WINDOW_MINUTES,
        )
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password), full_name=body.full_name)
    db.add(user)
    await db.flush()
    db.add(VoiceProfile(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return await _login_response(user, db, response)


@router.post("/login", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    response: Response = None,
    db: AsyncSession = Depends(get_db),
):
    if request is not None:
        await enforce_auth_limit(db, request, "login", subject=form.username)
    if len(form.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    result = await db.execute(select(User).where(User.email == form.username.strip().lower()))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return await _login_response(user, db, response)


@router.post("/google", response_model=TokenResponse)
async def google_sign_in(
    body: GoogleSignInRequest,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
    response: Response = None,
):
    """Create or sign in an account from a verified Google ID token."""
    if request is not None:
        await enforce_auth_limit(db, request, "google_login")
    claims = await verify_google_credential(body.credential)
    email = claims["email"].strip().lower()

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            email=email,
            full_name=claims.get("name") or email.split("@", 1)[0],
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            onboarded=False,
        )
        db.add(user)
        await db.flush()
        db.add(VoiceProfile(user_id=user.id))
        await db.commit()
        await db.refresh(user)
    return await _login_response(user, db, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_browser_session(request, db)
    if session and session.user_id == current_user.id:
        session.revoked_at = datetime.utcnow()
        await db.commit()
    clear_browser_session_cookie(response)


@router.get("/me")
async def me(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # After a page reload, return a fresh CSRF secret for the browser to keep
    # only in memory. The session cookie itself remains unreadable to JS.
    csrf_token = None
    session = await get_browser_session(request, db)
    if session:
        csrf_token = secrets.token_urlsafe(32)
        session.csrf_token_hash = hash_session_secret(csrf_token)
        session.last_seen_at = datetime.utcnow()
        await db.commit()
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "onboarded": current_user.onboarded,
        "avatar_url": current_user.avatar_url,
        "csrf_token": csrf_token,
    }
