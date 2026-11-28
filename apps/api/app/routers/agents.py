"""Tenant-scoped infrastructure agent credential management (P1-A7.1)."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import (
    get_current_user,
    require_organization_permission,
    require_session_csrf,
)
from app.db.session import get_db
from app.models.agents import InfrastructureAgentCredential
from app.models.identity import Organization, User
from app.schemas.agents import (
    AgentCredentialCreateRequest,
    AgentCredentialCreateResponse,
    AgentCredentialResponse,
)
from app.services.agents import (
    create_agent_credential,
    get_agent_credential,
    list_agent_credentials,
    revoke_agent_credential,
)
from app.services.audit import record_audit_event
from app.services.infrastructure import get_infrastructure_asset

router = APIRouter(prefix="/api/v1/organizations", tags=["infrastructure-agents"])


def _response(
    credential: InfrastructureAgentCredential,
    token: str | None = None,
) -> AgentCredentialResponse | AgentCredentialCreateResponse:
    """Build a safe response without exposing the stored digest."""
    values = {
        "id": credential.id,
        "organization_id": credential.organization_id,
        "asset_id": credential.asset_id,
        "created_by_user_id": credential.created_by_user_id,
        "name": credential.name,
        "token_prefix": credential.token_prefix,
        "created_at": credential.created_at,
        "expires_at": credential.expires_at,
        "revoked_at": credential.revoked_at,
    }
    if token is not None:
        return AgentCredentialCreateResponse(**values, token=token)
    return AgentCredentialResponse(**values)


@router.post(
    "/{organization_id}/infrastructure/assets/{asset_id}/agents",
    response_model=AgentCredentialCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent(
    payload: AgentCredentialCreateRequest,
    asset_id: UUID,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("infrastructure.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> AgentCredentialCreateResponse:
    """Issue one high-entropy asset credential; return its token once."""
    asset = get_infrastructure_asset(db, organization.id, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infrastructure asset not found",
        )

    try:
        created = create_agent_credential(
            db,
            organization_id=organization.id,
            asset_id=asset.id,
            created_by_user_id=actor.id,
            name=payload.name,
            ttl=timedelta(days=payload.expires_in_days),
        )
        record_audit_event(
            db,
            organization_id=organization.id,
            actor_user_id=actor.id,
            event_type="infrastructure.agent.credential.created",
            target_type="infrastructure_agent_credential",
            target_id=str(created.credential.id),
            details={
                "asset_id": str(asset.id),
                "name": created.credential.name,
                "expires_at": created.credential.expires_at.isoformat(),
            },
        )
        db.commit()
        db.refresh(created.credential)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent credential could not be created",
        ) from exc

    response = _response(created.credential, created.token)
    assert isinstance(response, AgentCredentialCreateResponse)
    return response


@router.get(
    "/{organization_id}/infrastructure/assets/{asset_id}/agents",
    response_model=list[AgentCredentialResponse],
)
def list_agents(
    asset_id: UUID,
    organization: Organization = Depends(
        require_organization_permission("infrastructure.read")
    ),
    db: Session = Depends(get_db),
) -> list[AgentCredentialResponse]:
    """List credential metadata for one authorized asset."""
    asset = get_infrastructure_asset(db, organization.id, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infrastructure asset not found",
        )
    credentials = list_agent_credentials(
        db,
        organization_id=organization.id,
        asset_id=asset.id,
    )
    return [_response(credential) for credential in credentials]


@router.delete(
    "/{organization_id}/infrastructure/assets/{asset_id}/agents/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_agent(
    asset_id: UUID,
    credential_id: UUID,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("infrastructure.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke a credential once; repeat requests are safe and idempotent."""
    asset = get_infrastructure_asset(db, organization.id, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infrastructure asset not found",
        )
    credential = get_agent_credential(
        db,
        organization_id=organization.id,
        asset_id=asset.id,
        credential_id=credential_id,
    )
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Infrastructure agent credential not found",
        )

    changed = revoke_agent_credential(db, credential)
    if changed:
        record_audit_event(
            db,
            organization_id=organization.id,
            actor_user_id=actor.id,
            event_type="infrastructure.agent.credential.revoked",
            target_type="infrastructure_agent_credential",
            target_id=str(credential.id),
            details={
                "asset_id": str(asset.id),
                "name": credential.name,
            },
        )
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
