"""Argon2id password hashing and local identity authentication (P1-A2.2)."""

from __future__ import annotations

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import User

_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
# A dummy Argon2id hash makes unknown-email and OIDC-only attempts pay a
# password-verification cost too, reducing account-enumeration timing leaks.
_DUMMY_PASSWORD_HASH = _password_hasher.hash("EII-dummy-password-not-a-user")


def hash_password(password: str) -> str:
    """Hash a new local password with Argon2id."""
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    if len(password) > 128:
        raise ValueError("Password must contain at most 128 characters")
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without exposing Argon2 parsing/verification errors."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return an active local-auth user, or None for every invalid case."""
    normalized_email = email.strip().lower()
    user = db.scalars(select(User).where(User.email == normalized_email)).one_or_none()
    stored_hash = user.password_hash if user and user.password_hash else _DUMMY_PASSWORD_HASH
    valid = verify_password(password, stored_hash)
    if not valid or user is None or not user.is_active or user.deleted_at is not None:
        return None
    return user
