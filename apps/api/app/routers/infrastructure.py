"""Organization-scoped infrastructure asset inventory API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import (
    get_current_user,
    require_organization_permission,
    require_session_csrf,
)
from app.db.session import get_db
from app.db.tenant_context import set_current_organization
from app.models.identity import Organization, User
from app.models.infrastructure import InfrastructureAsset
from app.schemas.infrastructure import (
    AssetStatus,
    AssetType,
    InfrastructureAssetCreateRequest,
    InfrastructureAssetResponse,
    InfrastructureAssetUpdateRequest,
)
from app.services.audit import record_audit_event
from app.services.infrastructure import (
    create_infrastructure_asset,
    get_infrastructure_asset,
    list_infrastructure_assets,
    soft_delete_infrastructure_asset,
    update_infrastructure_asset,
)

router = APIRouter(prefix="/api/v1/organizations", tags=["infrastructure"])


@router.get(
    "/{organization_id}/infrastructure/assets",
    response_model=list[InfrastructureAssetResponse],
)
def list_assets(
    organization: Organization = Depends(
        require_organization_permission("infrastructure.read")
    ),
    db: Session = Depends(get_db),
    asset_type: AssetType | None = Query(default=None),
    status_filter: AssetStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[InfrastructureAsset]:
    """List only non-deleted assets belonging to the authorized organization."""
    return list_infrastructure_assets(
        db,
        organization.id,
        asset_type=asset_type,
        status=status_filter,
        limit=limit,
    )


@router.get(
    "/{organization_id}/infrastructure/assets/{asset_id}",
    response_model=InfrastructureAssetResponse,
)
def get_asset(
    asset_id: UUID,
    organization: Organization = Depends(
        require_organization_permission("infrastructure.read")
    ),
    db: Session = Depends(get_db),
) -> InfrastructureAsset:
    """Read one asset after membership and infrastructure.read checks."""
    asset = get_infrastructure_asset(db, organization.id, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infrastructure asset not found",
        )
    return asset


@router.post(
    "/{organization_id}/infrastructure/assets",
    response_model=InfrastructureAssetResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_asset(
    payload: InfrastructureAssetCreateRequest,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("infrastructure.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> InfrastructureAsset:
    """Create an asset and its audit event in one database transaction."""
    try:
        asset = create_infrastructure_asset(
            db,
            organization.id,
            payload.model_dump(),
        )
        record_audit_event(
            db,
            organization_id=organization.id,
            actor_user_id=actor.id,
            event_type="infrastructure.asset.created",
            target_type="infrastructure_asset",
            target_id=str(asset.id),
            details={"asset_type": asset.asset_type, "status": asset.status},
        )
        db.commit()
        set_current_organization(db, organization.id, actor.id)
        db.refresh(asset)
        return asset
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this external_id already exists in this organization",
        ) from exc


@router.patch(
    "/{organization_id}/infrastructure/assets/{asset_id}",
    response_model=InfrastructureAssetResponse,
)
def update_asset(
    asset_id: UUID,
    payload: InfrastructureAssetUpdateRequest,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("infrastructure.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> InfrastructureAsset:
    """Update one tenant asset and append a redacted audit event atomically."""
    asset = get_infrastructure_asset(db, organization.id, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infrastructure asset not found",
        )

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return asset

    try:
        update_infrastructure_asset(db, asset, changes)
        record_audit_event(
            db,
            organization_id=organization.id,
            actor_user_id=actor.id,
            event_type="infrastructure.asset.updated",
            target_type="infrastructure_asset",
            target_id=str(asset.id),
            details={"changed_fields": sorted(changes)},
        )
        db.commit()
        set_current_organization(db, organization.id, actor.id)
        db.refresh(asset)
        return asset
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this external_id already exists in this organization",
        ) from exc


@router.delete(
    "/{organization_id}/infrastructure/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_asset(
    asset_id: UUID,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("infrastructure.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> Response:
    """Soft-delete an asset and append its audit event atomically."""
    asset = get_infrastructure_asset(db, organization.id, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infrastructure asset not found",
        )

    soft_delete_infrastructure_asset(db, asset)
    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=actor.id,
        event_type="infrastructure.asset.deleted",
        target_type="infrastructure_asset",
        target_id=str(asset.id),
        details={"asset_type": asset.asset_type, "status": asset.status},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
