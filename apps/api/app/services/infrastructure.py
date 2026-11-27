"""Tenant-scoped infrastructure asset inventory service."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.infrastructure import InfrastructureAsset
from app.schemas.infrastructure import AssetStatus, AssetType


def list_infrastructure_assets(
    db: Session,
    organization_id: UUID,
    *,
    asset_type: AssetType | None = None,
    status: AssetStatus | None = None,
    limit: int = 50,
) -> list[InfrastructureAsset]:
    """List non-deleted assets for exactly one organization."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")

    statement = (
        select(InfrastructureAsset)
        .where(InfrastructureAsset.organization_id == organization_id)
        .where(InfrastructureAsset.deleted_at.is_(None))
    )
    if asset_type is not None:
        statement = statement.where(InfrastructureAsset.asset_type == asset_type)
    if status is not None:
        statement = statement.where(InfrastructureAsset.status == status)

    statement = statement.order_by(
        InfrastructureAsset.updated_at.desc(),
        InfrastructureAsset.id.desc(),
    ).limit(limit)
    return list(db.scalars(statement).all())


def get_infrastructure_asset(
    db: Session,
    organization_id: UUID,
    asset_id: UUID,
) -> InfrastructureAsset | None:
    """Resolve one non-deleted asset only inside the supplied organization."""
    return db.scalar(
        select(InfrastructureAsset)
        .where(InfrastructureAsset.id == asset_id)
        .where(InfrastructureAsset.organization_id == organization_id)
        .where(InfrastructureAsset.deleted_at.is_(None))
    )


def create_infrastructure_asset(
    db: Session,
    organization_id: UUID,
    values: dict[str, object],
) -> InfrastructureAsset:
    """Insert an asset without committing the caller's transaction."""
    asset = InfrastructureAsset(organization_id=organization_id, **values)
    db.add(asset)
    db.flush()
    return asset


def update_infrastructure_asset(
    db: Session,
    asset: InfrastructureAsset,
    changes: dict[str, object],
) -> InfrastructureAsset:
    """Apply validated fields and flush without committing."""
    if not changes:
        return asset
    for field_name, value in changes.items():
        setattr(asset, field_name, value)
    asset.updated_at = datetime.now(timezone.utc)
    db.flush()
    return asset


def soft_delete_infrastructure_asset(
    db: Session,
    asset: InfrastructureAsset,
) -> InfrastructureAsset:
    """Hide an asset from normal reads while retaining its audit history."""
    now = datetime.now(timezone.utc)
    asset.deleted_at = now
    asset.updated_at = now
    db.flush()
    return asset
