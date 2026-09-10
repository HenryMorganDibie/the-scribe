import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    # Versioned tokens let us invalidate every bearer token from the old
    # localStorage-based session implementation during this security upgrade.
    to_encode.update({"exp": expire, "v": 2})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def hash_session_secret(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def create_browser_session(db: AsyncSession, user_id: str) -> tuple[str, str]:
    """Create an opaque cookie session and a separately supplied CSRF secret."""
    from app.models import UserSession

    token = secrets.token_urlsafe(48)
    csrf_token = secrets.token_urlsafe(32)
    db.add(UserSession(
        user_id=user_id,
        token_hash=hash_session_secret(token),
        csrf_token_hash=hash_session_secret(csrf_token),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.SESSION_EXPIRE_MINUTES),
    ))
    await db.commit()
    return token, csrf_token


async def get_browser_session(request: Request, db: AsyncSession):
    """Return the active opaque session for this request, if any."""
    from app.models import UserSession

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None
    result = await db.execute(
        select(UserSession).where(
            UserSession.token_hash == hash_session_secret(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


def set_browser_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_browser_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def require_csrf(request: Request, session) -> None:
    submitted = request.headers.get("X-CSRF-Token", "")
    if not submitted or not secrets.compare_digest(hash_session_secret(submitted), session.csrf_token_hash):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid security token")


async def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            if user_id is None or payload.get("v") != 2:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
    else:
        session = await get_browser_session(request, db)
        if not session:
            raise credentials_exception
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_csrf(request, session)
        user_id = session.user_id

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
