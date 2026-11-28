"""Tenant-scoped persistence helpers for infrastructure metrics."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.infrastructure_metrics import InfrastructureMetric


def list_infrastructure_metrics(
    db: Session,
    organization_id: UUID,
    asset_id: UUID,
    *,
    metric_name: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
) -> list[InfrastructureMetric]:
    """Return newest samples for one asset inside one authorized tenant."""
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")

    statement = (
        select(InfrastructureMetric)
        .where(InfrastructureMetric.organization_id == organization_id)
        .where(InfrastructureMetric.asset_id == asset_id)
    )
    if metric_name is not None:
        statement = statement.where(InfrastructureMetric.metric_name == metric_name)
    if since is not None:
        statement = statement.where(InfrastructureMetric.recorded_at >= since)
    if until is not None:
        statement = statement.where(InfrastructureMetric.recorded_at <= until)

    statement = statement.order_by(
        InfrastructureMetric.recorded_at.desc(),
        InfrastructureMetric.id.desc(),
    ).limit(limit)
    return list(db.scalars(statement).all())


def create_infrastructure_metric(
    db: Session,
    organization_id: UUID,
    asset_id: UUID,
    values: dict[str, object],
) -> InfrastructureMetric:
    """Insert one immutable sample without committing the caller's transaction."""
    metric = InfrastructureMetric(
        organization_id=organization_id,
        asset_id=asset_id,
        **values,
    )
    db.add(metric)
    db.flush()
    return metric
