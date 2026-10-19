"""Postgres-backed limits that work on every Render instance."""
import hashlib
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import SecurityEvent


def _hash(value: str) -> str:
    return hashlib.sha256(f"{settings.SECRET_KEY}:{value}".encode()).hexdigest()


def _client_ip(request: Request) -> str:
    """The client IP for per-IP limits.

    Client-supplied headers can't be trusted: anyone can send
    `x-forwarded-for: 1.2.3.4`. Each proxy we run behind *appends* the address
    it received the request from, so with TRUSTED_PROXY_HOPS = n the real
    client is the n-th entry from the right. 0 (the default) means no trusted
    proxy: use the socket peer. Vercel → Render needs 2 (see render.yaml).
    """
    hops = settings.TRUSTED_PROXY_HOPS
    if hops > 0:
        entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",") if e.strip()]
        if len(entries) >= hops:
            return entries[-hops]
    return request.client.host if request.client else "unknown"


async def _count(
    db: AsyncSession, action: str, cutoff: datetime, *, subject_hash: str | None = None,
    ip_hash: str | None = None, user_id: str | None = None,
) -> int:
    conditions = [SecurityEvent.action == action, SecurityEvent.created_at >= cutoff]
    if subject_hash is not None:
        conditions.append(SecurityEvent.subject_hash == subject_hash)
    if ip_hash is not None:
        conditions.append(SecurityEvent.ip_hash == ip_hash)
    if user_id is not None:
        conditions.append(SecurityEvent.user_id == user_id)
    return int((await db.execute(select(func.count(SecurityEvent.id)).where(*conditions))).scalar_one())


async def enforce_auth_limit(
    db: AsyncSession, request: Request, action: str, *, subject: str | None = None,
    limit: int | None = None, window_minutes: int | None = None,
) -> None:
    """Enforce independent per-IP and per-account throttles, then record one attempt."""
    limit = limit or settings.AUTH_RATE_LIMIT_ATTEMPTS
    window_minutes = window_minutes or settings.AUTH_RATE_LIMIT_WINDOW_MINUTES
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
    subject_hash = _hash(subject.strip().lower()) if subject else None
    ip_hash = _hash(_client_ip(request))
    ip_count = await _count(db, action, cutoff, ip_hash=ip_hash)
    subject_count = await _count(db, action, cutoff, subject_hash=subject_hash) if subject_hash else 0
    if ip_count >= limit or subject_count >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Please try again later.")
    db.add(SecurityEvent(action=action, subject_hash=subject_hash, ip_hash=ip_hash))
    await db.commit()


async def consume_user_quota(db: AsyncSession, user_id: str, action: str, limit: int) -> None:
    """Consume one daily action allowance before expensive work starts."""
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    if await _count(db, action, start, user_id=user_id) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily usage limit reached. Please try again tomorrow.")
    db.add(SecurityEvent(action=action, user_id=user_id))
    await db.commit()
