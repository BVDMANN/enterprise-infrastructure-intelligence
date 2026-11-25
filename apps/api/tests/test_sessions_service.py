"""Server-side opaque session lifecycle tests (P1-A2.1)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.identity import User
from app.models.sessions import AuthSession
from app.services.sessions import (
    create_session,
    get_active_session,
    revoke_session,
    verify_csrf_token,
)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(
        dbapi_connection, _connection_record
    ):  # noqa: ANN001, ANN202
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _user(db: Session, *, active: bool = True, deleted: bool = False) -> User:
    user = User(
        email="session@example.com",
        display_name="Session User",
        is_active=active,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    db.add(user)
    db.commit()
    return user


def test_create_session_persists_only_token_digests(db: Session) -> None:
    user = _user(db)
    credentials = create_session(db, user.id)
    db.commit()

    record = db.get(AuthSession, credentials.session_id)
    assert record is not None
    assert record.token_hash != credentials.session_token
    assert record.csrf_token_hash != credentials.csrf_token
    assert len(record.token_hash) == 64
    assert get_active_session(db, credentials.session_token) is not None


def test_unknown_or_missing_session_is_rejected(db: Session) -> None:
    assert get_active_session(db, None) is None
    assert get_active_session(db, "not-a-session") is None


def test_expired_session_is_rejected(db: Session) -> None:
    user = _user(db)
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    credentials = create_session(db, user.id, ttl=timedelta(minutes=5), now=created)
    db.commit()

    assert get_active_session(
        db, credentials.session_token, now=created + timedelta(minutes=5)
    ) is None


def test_revoked_session_is_rejected_and_revocation_is_idempotent(db: Session) -> None:
    user = _user(db)
    credentials = create_session(db, user.id)
    db.commit()

    assert revoke_session(db, credentials.session_token) is True
    db.commit()
    assert get_active_session(db, credentials.session_token) is None
    assert revoke_session(db, credentials.session_token) is False


@pytest.mark.parametrize("active,deleted", [(False, False), (True, True)])
def test_inactive_or_deleted_user_cannot_create_session(
    db: Session, active: bool, deleted: bool
) -> None:
    user = _user(db, active=active, deleted=deleted)
    with pytest.raises(ValueError, match="inactive user"):
        create_session(db, user.id)


def test_existing_session_is_rejected_after_user_deactivation(db: Session) -> None:
    user = _user(db)
    credentials = create_session(db, user.id)
    db.commit()

    user.is_active = False
    db.commit()
    assert get_active_session(db, credentials.session_token) is None


def test_csrf_token_is_bound_to_live_session(db: Session) -> None:
    user = _user(db)
    credentials = create_session(db, user.id)
    db.commit()

    assert verify_csrf_token(db, credentials.session_token, credentials.csrf_token)
    assert not verify_csrf_token(
        db, credentials.session_token, "wrong-csrf-token"
    )
    assert not verify_csrf_token(db, credentials.session_token, None)


def test_non_positive_session_ttl_is_rejected(db: Session) -> None:
    user = _user(db)
    with pytest.raises(ValueError, match="TTL must be positive"):
        create_session(db, user.id, ttl=timedelta(0))
