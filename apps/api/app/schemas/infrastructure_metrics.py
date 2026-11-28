"""Request and response schemas for infrastructure metric samples."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_METRIC_NAME = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")


class InfrastructureMetricCreateRequest(BaseModel):
    """Accept one bounded metric sample from an authenticated operator or agent."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(min_length=1, max_length=100)
    metric_value: Decimal = Field(max_digits=30, decimal_places=6)
    unit: str | None = Field(default=None, max_length=32)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("metric_name")
    @classmethod
    def normalize_metric_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _METRIC_NAME.fullmatch(normalized):
            raise ValueError(
                "metric_name must start with a letter and contain only "
                "lowercase letters, digits, dots, underscores or hyphens"
            )
        return normalized

    @field_validator("metric_value")
    @classmethod
    def require_finite_value(cls, value: Decimal) -> Decimal:
        if not value.is_finite():
            raise ValueError("metric_value must be finite")
        return value

    @field_validator("unit")
    @classmethod
    def normalize_unit(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("recorded_at")
    @classmethod
    def validate_recorded_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at must include a timezone")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError(
                "recorded_at cannot be more than five minutes in the future"
            )
        return value


class InfrastructureMetricResponse(BaseModel):
    """Persisted metric sample returned to an authorized tenant member."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    asset_id: UUID
    metric_name: str
    metric_value: Decimal
    unit: str | None
    ingestion_source: str
    recorded_at: datetime
    received_at: datetime
