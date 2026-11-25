"""Opaque server-side session lifecycle (P1-A2.1).

The browser receives random bearer/CSRF values once. Only SHA-256 digests
are stored. HTTP cookie flags, CSRF Origin checks and OIDC callbacks belong
to the API-router integration sub-lot and are not implied by this service.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import User
from app.models.sessions import AuthSession


@dataclass(frozen=True)
class SessionCredentials:
    """One-time plaintext credentials returned when a session is created."""

    session_id: UUID
    session_token: str
    csrf_token: str
    expires_at: datetime


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    """Normalize SQLite's naive timestamps and PostgreSQL aware timestamps."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return _utc(current)


def create_session(
    db: Session,
    user_id: UUID,
    *,
    ttl: timedelta = timedelta(hours=8),
    now: datetime | None = None,
) -> SessionCredentials:
    """Create a session for an active user; caller owns transaction commit."""
    if ttl <= timedelta(0):
        raise ValueError("Session TTL must be positive")

    user = db.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise ValueError("Cannot create a session for an inactive user")

    created_at = _now(now)
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = created_at + ttl
    record = AuthSession(
        user_id=user_id,
        token_hash=_digest(session_token),
        csrf_token_hash=_digest(csrf_token),
        created_at=created_at,
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()
    return SessionCredentials(
        session_id=record.id,
        session_token=session_token,
        csrf_token=csrf_token,
        expires_at=expires_at,
    )


def get_active_session(
    db: Session, session_token: str | None, *, now: datetime | None = None
) -> AuthSession | None:
    """Return a valid session only when its user is still active."""
    if not session_token:
        return None

    statement = (
        select(AuthSession)
        .join(User, User.id == AuthSession.user_id)
        .where(AuthSession.token_hash == _digest(session_token))
        .where(AuthSession.revoked_at.is_(None))
        .where(User.is_active.is_(True))
        .where(User.deleted_at.is_(None))
    )
    record = db.scalars(statement).one_or_none()
    if record is None or _utc(record.expires_at) <= _now(now):
        return None
    return record


def verify_csrf_token(
    db: Session,
    session_token: str | None,
    csrf_token: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    """Constant-time CSRF token check against a live session."""
    if not csrf_token:
        return False
    record = get_active_session(db, session_token, now=now)
    if record is None:
        return False
    return hmac.compare_digest(record.csrf_token_hash, _digest(csrf_token))


def revoke_session(
    db: Session, session_token: str | None, *, now: datetime | None = None
) -> bool:
    """Revoke a known session; caller owns transaction commit."""
    if not session_token:
        return False
    statement = select(AuthSession).where(
        AuthSession.token_hash == _digest(session_token)
    )
    record = db.scalars(statement).one_or_none()
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = _now(now)
    db.flush()
    return True
