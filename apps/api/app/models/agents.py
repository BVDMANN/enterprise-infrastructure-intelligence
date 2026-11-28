"""Revocable, asset-scoped infrastructure agent credentials (P1-A7.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InfrastructureAgentCredential(Base):
    """One revocable credential delegated to an asset by an active tenant member.

    Only a SHA-256 digest and a short display prefix are stored. The plaintext
    token is returned once at creation and is never persisted or audited.
    """

    __tablename__ = "infrastructure_agent_credentials"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "asset_id"],
            ["infrastructure_assets.organization_id", "infrastructure_assets.id"],
            name="fk_agent_credentials_organization_asset",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("token_hash", name="uq_agent_credentials_token_hash"),
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_agent_credentials_name_nonempty",
        ),
        CheckConstraint(
            "length(token_hash) = 64",
            name="ck_agent_credentials_token_hash_length",
        ),
        CheckConstraint(
            "length(token_prefix) BETWEEN 1 AND 24",
            name="ck_agent_credentials_token_prefix_length",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_agent_credentials_expiry_after_creation",
        ),
        Index(
            "ix_agent_credentials_organization_asset_created",
            "organization_id",
            "asset_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_agent_credentials_created_by_user", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
