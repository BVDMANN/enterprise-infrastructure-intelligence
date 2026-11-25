"""Argon2id and local identity authentication tests (P1-A2.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.identity import User
from app.services.passwords import authenticate_user, hash_password, verify_password


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):  # noqa: ANN001, ANN202
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


def _user(
    db: Session, *, active: bool = True, deleted: bool = False, mfa_enabled: bool = False
) -> User:
    user = User(
        email="local@example.com",
        display_name="Local User",
        password_hash=hash_password("correct-horse-battery"),
        is_active=active,
        mfa_enabled=mfa_enabled,
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    db.add(user)
    db.commit()
    return user


def test_argon2id_hash_is_not_plaintext_and_verifies() -> None:
    password = "correct-horse-battery"
    encoded = hash_password(password)
    assert encoded != password
    assert encoded.startswith("$argon2id$")
    assert verify_password(password, encoded)
    assert not verify_password("wrong-password", encoded)


def test_password_policy_rejects_short_and_long_values() -> None:
    with pytest.raises(ValueError, match="at least 12"):
        hash_password("short")
    with pytest.raises(ValueError, match="at most 128"):
        hash_password("x" * 129)


def test_authentication_normalizes_email(db: Session) -> None:
    user = _user(db)
    assert (
        authenticate_user(db, "  LOCAL@EXAMPLE.COM ", "correct-horse-battery").id
        == user.id
    )


def test_authentication_rejects_wrong_password_and_unknown_user(db: Session) -> None:
    _user(db)
    assert authenticate_user(db, "local@example.com", "wrong-password") is None
    assert authenticate_user(db, "unknown@example.com", "wrong-password") is None


@pytest.mark.parametrize(
    "active,deleted,mfa_enabled",
    [(False, False, False), (True, True, False), (True, False, True)],
)
def test_authentication_rejects_inactive_deleted_or_mfa_user(
    db: Session, active: bool, deleted: bool, mfa_enabled: bool
) -> None:
    _user(db, active=active, deleted=deleted, mfa_enabled=mfa_enabled)
    assert authenticate_user(db, "local@example.com", "correct-horse-battery") is None


def test_oidc_only_user_cannot_use_local_password_login(db: Session) -> None:
    user = User(email="oidc@example.com", display_name="OIDC User", password_hash=None)
    db.add(user)
    db.commit()
    assert authenticate_user(db, "oidc@example.com", "some-password") is None
