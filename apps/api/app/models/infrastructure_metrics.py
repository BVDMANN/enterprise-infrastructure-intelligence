"""Append-only infrastructure metric samples (P1-A6.3)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InfrastructureMetric(Base):
    """One immutable measurement attached to an organization-owned asset."""

    __tablename__ = "infrastructure_metrics"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "asset_id"],
            ["infrastructure_assets.organization_id", "infrastructure_assets.id"],
            name="fk_infrastructure_metrics_organization_asset",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "length(trim(metric_name)) > 0",
            name="ck_infrastructure_metrics_name_nonempty",
        ),
        CheckConstraint(
            "metric_name = lower(metric_name)",
            name="ck_infrastructure_metrics_name_lowercase",
        ),
        CheckConstraint(
            "unit IS NULL OR length(trim(unit)) > 0",
            name="ck_infrastructure_metrics_unit_nonempty",
        ),
        Index(
            "ix_infrastructure_metrics_organization_asset_recorded",
            "organization_id",
            "asset_id",
            "recorded_at",
        ),
        Index(
            "ix_infrastructure_metrics_organization_name_recorded",
            "organization_id",
            "metric_name",
            "recorded_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(30, 6), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
