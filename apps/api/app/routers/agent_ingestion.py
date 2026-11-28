"""Bearer-authenticated infrastructure agent ingestion endpoints (P1-A7.2)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agents import InfrastructureAgentCredential
from app.models.infrastructure import InfrastructureAsset
from app.schemas.agent_ingestion import (
    AgentHeartbeatResponse,
    AgentMetricBatchRequest,
    AgentMetricBatchResponse,
)
from app.services.agents import authenticate_agent_credential
from app.services.audit import record_audit_event
from app.services.infrastructure import get_infrastructure_asset
from app.services.infrastructure_metrics import create_infrastructure_metric

router = APIRouter(prefix="/api/v1/agent", tags=["agent-ingestion"])
_bearer = HTTPBearer(auto_error=False)


def get_authenticated_agent(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> InfrastructureAgentCredential:
    """Resolve a live bearer credential and establish its tenant DB context."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent credential",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credential = authenticate_agent_credential(db, credentials.credentials)
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent credential",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Hold the credential row lock until the request commits. A concurrent
    # revocation then serializes with this request instead of racing a batch.
    live_credential_id = db.scalar(
        select(InfrastructureAgentCredential.id)
        .where(InfrastructureAgentCredential.id == credential.id)
        .where(InfrastructureAgentCredential.revoked_at.is_(None))
        .where(InfrastructureAgentCredential.expires_at > datetime.now(timezone.utc))
        .with_for_update()
    )
    if live_credential_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent credential",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credential


def _require_bound_asset(
    db: Session,
    credential: InfrastructureAgentCredential,
) -> InfrastructureAsset:
    """Resolve only the asset embedded in the authenticated credential."""
    asset = get_infrastructure_asset(
        db,
        credential.organization_id,
        credential.asset_id,
    )
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent credential",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return asset


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
)
def heartbeat(
    response: Response,
    credential: InfrastructureAgentCredential = Depends(get_authenticated_agent),
    db: Session = Depends(get_db),
) -> AgentHeartbeatResponse:
    """Update last_seen_at without changing the operator-managed asset status."""
    asset = _require_bound_asset(db, credential)
    asset_id = credential.asset_id
    received_at = datetime.now(timezone.utc)
    asset.last_seen_at = received_at
    db.commit()

    response.headers["Cache-Control"] = "no-store"
    return AgentHeartbeatResponse(asset_id=asset_id, received_at=received_at)


@router.post(
    "/metrics",
    response_model=AgentMetricBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_metrics(
    payload: AgentMetricBatchRequest,
    response: Response,
    credential: InfrastructureAgentCredential = Depends(get_authenticated_agent),
    db: Session = Depends(get_db),
) -> AgentMetricBatchResponse:
    """Persist one bounded batch for the asset bound to the bearer credential."""
    asset = _require_bound_asset(db, credential)
    organization_id = credential.organization_id
    asset_id = credential.asset_id
    actor_user_id = credential.created_by_user_id
    credential_id = credential.id
    received_at = datetime.now(timezone.utc)

    try:
        for sample in payload.samples:
            values = sample.model_dump()
            values["ingestion_source"] = "agent_api"
            values["received_at"] = received_at
            create_infrastructure_metric(
                db,
                organization_id,
                asset_id,
                values,
            )

        asset.last_seen_at = received_at
        record_audit_event(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type="infrastructure.agent.metrics.ingested",
            target_type="infrastructure_asset",
            target_id=str(asset_id),
            occurred_at=received_at,
            details={
                "actor_type": "infrastructure_agent",
                "agent_credential_id": str(credential_id),
                "sample_count": len(payload.samples),
                "ingestion_source": "agent_api",
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The agent batch could not be persisted",
        ) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent credential",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    response.headers["Cache-Control"] = "no-store"
    return AgentMetricBatchResponse(
        asset_id=asset_id,
        accepted=len(payload.samples),
        received_at=received_at,
    )
