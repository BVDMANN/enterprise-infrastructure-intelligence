"""Member invitations by manual link (P1-A1 completion).

PHASE1_PLAN.md D5: no transactional email in PHASE 1. The invitation
token is returned once at creation; the inviter copies the accept link
manually. Only the SHA-256 digest of the token is persisted, and the
token never appears in audit details or in any response after creation.

Acceptance has two modes, both authorized by the invitation token
itself (the tenant comes from the invitation, never from a value
supplied by the caller):
- authenticated: the caller has a live session whose email matches the
  invitation email (this is the only path for MFA users);
- password: no session — the caller proves ownership of the invited
  email with its password (existing account) or creates the account
  with a display name and a password (new account).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import Invitation, Membership, Organization, User
from app.models.rbac import Role
from app.services.audit import record_audit_event
from app.services.passwords import authenticate_user, hash_password

DEFAULT_EXPIRY_DAYS = 7
MAX_EXPIRY_DAYS = 30
MAX_EMAIL_LENGTH = 320
MAX_DISPLAY_NAME_LENGTH = 255


class InvitationNotFoundError(ValueError):
    """No pending invitation matches (mapped to HTTP 404, no leak)."""


class InvitationConflictError(ValueError):
    """Duplicate pending invitation / already a member (HTTP 409)."""


class InvitationForbiddenError(ValueError):
    """Authenticated user is not the invitee (HTTP 403)."""


class InvitationUnauthorizedError(ValueError):
    """Bad or missing password for an existing account (HTTP 401)."""


class InvitationValidationError(ValueError):
    """Invalid email, role or expiry (HTTP 422)."""


def hash_invitation_token(token: str) -> str:
    """SHA-256 digest of an invitation token (the only stored form)."""
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _utc(value: datetime) -> datetime:
    """Normalize a stored datetime to UTC (SQLite returns naive values)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def invitation_status(invitation: Invitation, *, now: datetime | None = None) -> str:
    """Pending, accepted, revoked or expired, from the stored timestamps."""
    current = now or datetime.now(timezone.utc)
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.revoked_at is not None:
        return "revoked"
    if _utc(invitation.expires_at) <= current:
        return "expired"
    return "pending"


def _is_pending(invitation: Invitation, *, now: datetime | None = None) -> bool:
    return invitation_status(invitation, now=now) == "pending"


def _find_pending_invitation(db: Session, *, token_hash: str) -> Invitation | None:
    invitation = db.scalar(
        select(Invitation).where(Invitation.token_hash == token_hash)
    )
    if invitation is None or not _is_pending(invitation):
        return None
    return invitation


def create_invitation(
    db: Session,
    *,
    inviter: User,
    organization: Organization,
    email: str,
    role_id: UUID,
    expires_in_days: int = DEFAULT_EXPIRY_DAYS,
) -> tuple[Invitation, str]:
    """Create a pending invitation and return (invitation, token).

    The token is returned once: the caller (HTTP route) is responsible
    for showing it to the inviter exactly once. The caller owns the
    transaction: nothing is committed here.
    """
    normalized_email = email.strip().lower()
    if (
        "@" not in normalized_email
        or len(normalized_email) < 3
        or len(normalized_email) > MAX_EMAIL_LENGTH
    ):
        raise InvitationValidationError("Invalid email address")
    if not 1 <= expires_in_days <= MAX_EXPIRY_DAYS:
        raise InvitationValidationError("Expiry must be between 1 and 30 days")

    role = db.scalar(
        select(Role).where(
            Role.id == role_id,
            Role.organization_id == organization.id,
        )
    )
    if role is None:
        raise InvitationNotFoundError("Role not found in organization")

    already_member = db.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization.id)
        .where(User.email == normalized_email)
    )
    if already_member is not None:
        raise InvitationConflictError("User is already a member of this organization")

    now = datetime.now(timezone.utc)
    pending = db.scalar(
        select(Invitation.id)
        .where(Invitation.organization_id == organization.id)
        .where(Invitation.email == normalized_email)
        .where(Invitation.revoked_at.is_(None))
        .where(Invitation.accepted_at.is_(None))
        .where(Invitation.expires_at > now)
    )
    if pending is not None:
        raise InvitationConflictError(
            "A pending invitation already exists for this email"
        )

    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        organization_id=organization.id,
        email=normalized_email,
        role_id=role.id,
        token_hash=hash_invitation_token(token),
        expires_at=now + timedelta(days=expires_in_days),
        invited_by_user_id=inviter.id,
    )
    db.add(invitation)
    db.flush()

    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=inviter.id,
        event_type="invitation.created",
        target_type="invitation",
        target_id=str(invitation.id),
        details={
            "invitation_id": str(invitation.id),
            "email": normalized_email,
            "role_id": str(role.id),
            "role_name": role.name,
        },
    )
    return invitation, token


def revoke_invitation(
    db: Session,
    *,
    actor: User,
    organization: Organization,
    invitation: Invitation,
) -> bool:
    """Revoke an invitation. Returns True when it transitioned to revoked.

    Revoking an already revoked invitation is a no-op (False, no new
    audit event). Revoking an accepted invitation is refused.
    """
    if invitation.accepted_at is not None:
        raise InvitationConflictError("Invitation was already accepted")
    if invitation.revoked_at is not None:
        return False

    invitation.revoked_at = datetime.now(timezone.utc)
    db.flush()
    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=actor.id,
        event_type="invitation.revoked",
        target_type="invitation",
        target_id=str(invitation.id),
        details={
            "invitation_id": str(invitation.id),
            "email": invitation.email,
        },
    )
    return True


def accept_invitation(
    db: Session,
    *,
    token: str,
    display_name: str | None = None,
    password: str | None = None,
    session_user: User | None = None,
) -> tuple[Invitation, Membership, Organization, User]:
    """Accept a pending invitation and return (invitation, membership, org, user).

    The caller owns the transaction: nothing is committed here.
    """
    invitation = _find_pending_invitation(db, token_hash=hash_invitation_token(token))
    if invitation is None:
        raise InvitationNotFoundError("Invitation not found or no longer valid")

    organization = db.get(Organization, invitation.organization_id)
    if organization is None or organization.deleted_at is not None:
        raise InvitationNotFoundError("Invitation not found or no longer valid")

    if session_user is not None:
        if session_user.email != invitation.email:
            raise InvitationForbiddenError(
                "This invitation was sent to another email address"
            )
        user = session_user
    else:
        if password is None:
            raise InvitationUnauthorizedError(
                "Password is required to accept this invitation"
            )
        existing = db.scalar(select(User).where(User.email == invitation.email))
        if existing is not None:
            authenticated = authenticate_user(db, invitation.email, password)
            if authenticated is None:
                raise InvitationUnauthorizedError("Invalid credentials")
            user = authenticated
        else:
            if (
                display_name is None
                or not display_name.strip()
                or len(display_name.strip()) > MAX_DISPLAY_NAME_LENGTH
            ):
                raise InvitationValidationError(
                    "Display name is required to create an account"
                )
            try:
                password_hash = hash_password(password)
            except ValueError as exc:
                raise InvitationValidationError(str(exc)) from exc
            user = User(
                email=invitation.email,
                display_name=display_name.strip(),
                password_hash=password_hash,
                is_active=True,
            )
            db.add(user)
            db.flush()

    existing_membership = db.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization.id,
            Membership.user_id == user.id,
        )
    )
    if existing_membership is not None:
        raise InvitationConflictError("User is already a member of this organization")

    role = db.scalar(
        select(Role).where(
            Role.id == invitation.role_id,
            Role.organization_id == organization.id,
        )
    )
    if role is None:
        raise InvitationNotFoundError("Invitation role no longer exists")

    membership = Membership(
        organization_id=organization.id,
        user_id=user.id,
        role_id=role.id,
    )
    db.add(membership)
    db.flush()

    invitation.accepted_at = datetime.now(timezone.utc)
    invitation.accepted_user_id = user.id
    db.flush()

    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=user.id,
        event_type="invitation.accepted",
        target_type="invitation",
        target_id=str(invitation.id),
        details={
            "invitation_id": str(invitation.id),
            "email": invitation.email,
            "role_id": str(role.id),
            "role_name": role.name,
        },
    )
    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=user.id,
        event_type="membership.created",
        target_type="membership",
        target_id=str(membership.id),
        details={
            "target_user_id": str(user.id),
            "role_id": str(role.id),
            "role_name": role.name,
            "via_invitation_id": str(invitation.id),
        },
    )
    return invitation, membership, organization, user
