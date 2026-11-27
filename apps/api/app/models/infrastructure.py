"""Tenant-scoped infrastructure asset inventory (P1-A6.1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

ASSET_TYPES = (
    "server",
    "virtual_machine",
    "container",
    "cluster",
    "database",
    "network",
    "storage",
    "cloud_resource",
    "service",
    "other",
)
ASSET_STATUSES = ("unknown", "healthy", "degraded", "unhealthy", "offline")
ATTRIBUTES_TYPE = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InfrastructureAsset(Base):
    """An inventory record owned by exactly one organization.

    This is inventory metadata, not a telemetry sample or connector
    credential. Attributes are bounded and reject secrets at the API
    boundary. Tenant authorization is enforced by API RBAC dependencies;
    PostgreSQL RLS is not enabled by this migration.
    """

    __tablename__ = "infrastructure_assets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "external_id",
            name="uq_infrastructure_assets_organization_external_id",
        ),
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_infrastructure_assets_organization_id_id",
        ),
        CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_infrastructure_assets_name_nonempty",
        ),
        CheckConstraint(
            "asset_type IN ('server', 'virtual_machine', 'container', 'cluster', "
            "'database', 'network', 'storage', 'cloud_resource', 'service', 'other')",
            name="ck_infrastructure_assets_type",
        ),
        CheckConstraint(
            "status IN ('unknown', 'healthy', 'degraded', 'unhealthy', 'offline')",
            name="ck_infrastructure_assets_status",
        ),
        CheckConstraint(
            "external_id IS NULL OR length(trim(external_id)) > 0",
            name="ck_infrastructure_assets_external_id_nonempty",
        ),
        CheckConstraint(
            "provider IS NULL OR length(trim(provider)) > 0",
            name="ck_infrastructure_assets_provider_nonempty",
        ),
        CheckConstraint(
            "region IS NULL OR length(trim(region)) > 0",
            name="ck_infrastructure_assets_region_nonempty",
        ),
        Index(
            "ix_infrastructure_assets_organization_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_infrastructure_assets_organization_type",
            "organization_id",
            "asset_type",
        ),
        Index(
            "ix_infrastructure_assets_organization_updated_at",
            "organization_id",
            "updated_at",
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown", server_default=text("'unknown'")
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        ATTRIBUTES_TYPE,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"InfrastructureAsset(id={self.id!r}, "
            f"organization_id={self.organization_id!r}, name={self.name!r})"
        )
