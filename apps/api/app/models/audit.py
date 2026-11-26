"""Tenant-scoped append-only audit event model (P1-A5)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

DETAILS_TYPE = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(Base):
    """Immutable record attributed to an active member of one organization."""

    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_audit_events_organization_actor_membership",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "length(trim(event_type)) > 0",
            name="ck_audit_events_event_type_nonempty",
        ),
        CheckConstraint(
            "target_type IS NULL OR length(trim(target_type)) > 0",
            name="ck_audit_events_target_type_nonempty",
        ),
        CheckConstraint(
            "request_id IS NULL OR length(trim(request_id)) > 0",
            name="ck_audit_events_request_id_nonempty",
        ),
        Index(
            "ix_audit_events_organization_occurred_at",
            "organization_id",
            "occurred_at",
        ),
        Index(
            "ix_audit_events_organization_actor_occurred_at",
            "organization_id",
            "actor_user_id",
            "occurred_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        DETAILS_TYPE,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
