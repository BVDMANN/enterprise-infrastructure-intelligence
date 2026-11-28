"""Tenant-scoped audit event writer and reader (P1-A5).

The caller owns transaction commit/rollback. This module never commits.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tenant_context import set_current_organization

from app.models.audit import AuditEvent
from app.models.identity import Membership, Organization, User

MAX_DETAILS_BYTES = 16 * 1024
SENSITIVE_DETAIL_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "csrf",
    "apikey",
    "privatekey",
)


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("Audit detail keys must be strings")
            if any(
                fragment in _normalized_key(key)
                for fragment in SENSITIVE_DETAIL_KEY_FRAGMENTS
            ):
                return True
            if _contains_sensitive_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _validated_details(details: dict[str, Any] | None) -> dict[str, Any]:
    if details is None:
        return {}
    if not isinstance(details, dict):
        raise ValueError("Audit details must be a JSON object")
    if _contains_sensitive_key(details):
        raise ValueError("Audit details must not contain credentials or secrets")
    try:
        encoded = json.dumps(
            details,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Audit details must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_DETAILS_BYTES:
        raise ValueError("Audit details exceed the 16 KiB limit")
    return details


def record_audit_event(
    db: Session,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    event_type: str,
    target_type: str | None = None,
    target_id: str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> AuditEvent:
    """Append one event for an active user with a membership in the tenant.

    The database composite foreign key preserves the actor/tenant relationship
    after insertion. PostgreSQL triggers reject UPDATE, DELETE and TRUNCATE.
    """
    normalized_event_type = event_type.strip().lower()
    if not normalized_event_type or len(normalized_event_type) > 100:
        raise ValueError("event_type must contain between 1 and 100 characters")

    normalized_target_type = target_type.strip().lower() if target_type else None
    if normalized_target_type is not None and len(normalized_target_type) > 100:
        raise ValueError("target_type must contain at most 100 characters")

    normalized_target_id = target_id.strip() if target_id else None
    if normalized_target_id is not None and len(normalized_target_id) > 255:
        raise ValueError("target_id must contain at most 255 characters")

    normalized_request_id = request_id.strip() if request_id else None
    if normalized_request_id is not None and len(normalized_request_id) > 128:
        raise ValueError("request_id must contain at most 128 characters")

    if occurred_at is not None and occurred_at.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")

    membership_id = db.scalar(
        select(Membership.id)
        .join(
            Organization,
            Organization.id == Membership.organization_id,
        )
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == organization_id)
        .where(Membership.user_id == actor_user_id)
        .where(Organization.deleted_at.is_(None))
        .where(User.is_active.is_(True))
        .where(User.deleted_at.is_(None))
    )
    if membership_id is None:
        raise ValueError("Audit actor must be an active member of the organization")

    set_current_organization(db, organization_id)
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        event_type=normalized_event_type,
        target_type=normalized_target_type,
        target_id=normalized_target_id,
        request_id=normalized_request_id,
        details=_validated_details(details),
        occurred_at=occurred_at or datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    return event


def list_audit_events(
    db: Session,
    organization_id: UUID,
    *,
    limit: int = 50,
) -> list[AuditEvent]:
    """List newest events for one already-authorized organization."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    set_current_organization(db, organization_id)
    statement = (
        select(AuditEvent)
        .where(AuditEvent.organization_id == organization_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return list(db.scalars(statement).all())
