"""Request and response contracts for infrastructure agent ingestion."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.infrastructure_metrics import InfrastructureMetricCreateRequest


class AgentMetricBatchRequest(BaseModel):
    """A bounded, all-or-nothing batch of metric samples."""

    model_config = ConfigDict(extra="forbid")

    samples: list[InfrastructureMetricCreateRequest] = Field(
        min_length=1,
        max_length=100,
    )


class AgentHeartbeatResponse(BaseModel):
    """Acknowledgement of a persisted agent heartbeat."""

    asset_id: UUID
    received_at: datetime


class AgentMetricBatchResponse(BaseModel):
    """Acknowledgement of a persisted batch; metric values are not echoed."""

    asset_id: UUID
    accepted: int = Field(ge=1, le=100)
    received_at: datetime
