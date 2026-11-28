"""Asset-scoped infrastructure agent credential lifecycle (P1-A7.1)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tenant_context import (
    set_current_agent_token_hash,
    set_current_organization,
)
from app.models.agents import InfrastructureAgentCredential
from app.models.identity import Membership, Organization, User
from app.models.infrastructure import InfrastructureAsset


AGENT_TOKEN_PREFIX = "eii_agent_"
MAX_CREDENTIAL_TTL = timedelta(days=365)


@dataclass(frozen=True)
class CreatedAgentCredential:
    """Credential record plus the one-time plaintext token."""

    credential: InfrastructureAgentCredential
    token: str


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_agent_credential(
    db: Session,
    *,
    organization_id: UUID,
    asset_id: UUID,
    created_by_user_id: UUID,
    name: str,
    ttl: timedelta = timedelta(days=90),
    now: datetime | None = None,
) -> CreatedAgentCredential:
    """Create a high-entropy token; caller owns commit/rollback."""
    if ttl <= timedelta(0) or ttl > MAX_CREDENTIAL_TTL:
        raise ValueError("Agent credential TTL must be between 1 second and 365 days")
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 128:
        raise ValueError("Agent name must contain between 1 and 128 characters")

    created_at = _utc(now or datetime.now(timezone.utc))
    token = AGENT_TOKEN_PREFIX + secrets.token_urlsafe(32)
    credential = InfrastructureAgentCredential(
        organization_id=organization_id,
        asset_id=asset_id,
        created_by_user_id=created_by_user_id,
        name=normalized_name,
        token_hash=_digest(token),
        token_prefix=token[:20],
        created_at=created_at,
        expires_at=created_at + ttl,
    )
    db.add(credential)
    db.flush()
    return CreatedAgentCredential(credential=credential, token=token)


def list_agent_credentials(
    db: Session,
    *,
    organization_id: UUID,
    asset_id: UUID,
) -> list[InfrastructureAgentCredential]:
    """List credential metadata for one already-authorized asset."""
    statement = (
        select(InfrastructureAgentCredential)
        .where(InfrastructureAgentCredential.organization_id == organization_id)
        .where(InfrastructureAgentCredential.asset_id == asset_id)
        .order_by(
            InfrastructureAgentCredential.created_at.desc(),
            InfrastructureAgentCredential.id.desc(),
        )
    )
    return list(db.scalars(statement).all())


def get_agent_credential(
    db: Session,
    *,
    organization_id: UUID,
    asset_id: UUID,
    credential_id: UUID,
) -> InfrastructureAgentCredential | None:
    """Resolve a credential only within the authorized organization and asset."""
    return db.scalar(
        select(InfrastructureAgentCredential)
        .where(InfrastructureAgentCredential.id == credential_id)
        .where(InfrastructureAgentCredential.organization_id == organization_id)
        .where(InfrastructureAgentCredential.asset_id == asset_id)
    )


def revoke_agent_credential(
    db: Session,
    credential: InfrastructureAgentCredential,
    *,
    now: datetime | None = None,
) -> bool:
    """Revoke once; repeated calls are idempotent and do not commit."""
    if credential.revoked_at is not None:
        return False
    credential.revoked_at = _utc(now or datetime.now(timezone.utc))
    db.flush()
    return True


def authenticate_agent_credential(
    db: Session,
    token: str | None,
    *,
    now: datetime | None = None,
) -> InfrastructureAgentCredential | None:
    """Resolve a live token and establish its delegated tenant context.

    The PostgreSQL RLS lookup policy exposes at most the row matching the
    transaction-local token digest. The credential is then accepted only while
    its enrolling user, organization, membership and asset remain active.
    """
    if (
        not token
        or not token.startswith(AGENT_TOKEN_PREFIX)
        or len(token) > 128
    ):
        return None

    token_hash = _digest(token)
    set_current_agent_token_hash(db, token_hash)
    try:
        credential = db.scalars(
            select(InfrastructureAgentCredential)
            .where(InfrastructureAgentCredential.token_hash == token_hash)
            .where(InfrastructureAgentCredential.revoked_at.is_(None))
            .where(
                InfrastructureAgentCredential.expires_at
                > _utc(now or datetime.now(timezone.utc))
            )
        ).one_or_none()
    finally:
        set_current_agent_token_hash(db, None)

    if credential is None or not hmac.compare_digest(
        credential.token_hash, token_hash
    ):
        return None

    set_current_organization(
        db,
        credential.organization_id,
        credential.created_by_user_id,
    )
    active_membership = db.scalar(
        select(Membership.id)
        .join(User, User.id == Membership.user_id)
        .join(Organization, Organization.id == Membership.organization_id)
        .join(
            InfrastructureAsset,
            (InfrastructureAsset.id == credential.asset_id)
            & (InfrastructureAsset.organization_id == credential.organization_id),
        )
        .where(Membership.organization_id == credential.organization_id)
        .where(Membership.user_id == credential.created_by_user_id)
        .where(User.is_active.is_(True))
        .where(User.deleted_at.is_(None))
        .where(Organization.deleted_at.is_(None))
        .where(InfrastructureAsset.deleted_at.is_(None))
    )
    if active_membership is None:
        return None
    return credential
