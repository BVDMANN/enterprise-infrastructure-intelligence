"""Request and response schemas for infrastructure asset inventory."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AssetType = Literal[
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
]
AssetStatus = Literal["unknown", "healthy", "degraded", "unhealthy", "offline"]

SENSITIVE_ATTRIBUTE_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "authorization",
    "cookie",
    "csrf",
    "apikey",
    "accesskey",
    "credential",
    "bearer",
    "session",
    "privatekey",
    "sshkey",
)
MAX_ATTRIBUTES_BYTES = 16 * 1024


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _contains_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError("Asset attribute keys must be strings")
            normalized = _normalized_key(key)
            if any(
                fragment in normalized for fragment in SENSITIVE_ATTRIBUTE_FRAGMENTS
            ):
                return True
            if _contains_sensitive_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def validate_asset_attributes(value: dict[str, Any]) -> dict[str, Any]:
    """Reject credentials and non-JSON or oversized inventory attributes."""
    if not isinstance(value, dict):
        raise ValueError("Asset attributes must be a JSON object")
    if _contains_sensitive_key(value):
        raise ValueError("Asset attributes must not contain credentials or secrets")
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("Asset attributes must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_ATTRIBUTES_BYTES:
        raise ValueError("Asset attributes exceed the 16 KiB limit")
    return value


def _aware_timestamp(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("last_seen_at must be timezone-aware")
    return value


class InfrastructureAssetCreateRequest(BaseModel):
    """Create one inventory asset inside the authorized organization."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    asset_type: AssetType
    external_id: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    status: AssetStatus = "unknown"
    attributes: dict[str, Any] = Field(default_factory=dict)
    last_seen_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized

    @field_validator("external_id", "provider", "region")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("attributes")
    @classmethod
    def validate_attributes_field(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_asset_attributes(value)

    @field_validator("last_seen_at")
    @classmethod
    def validate_last_seen_at(cls, value: datetime | None) -> datetime | None:
        return _aware_timestamp(value)


class InfrastructureAssetUpdateRequest(BaseModel):
    """Update only the supplied inventory fields; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    asset_type: AssetType | None = None
    external_id: str | None = Field(default=None, max_length=255)
    provider: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    status: AssetStatus | None = None
    attributes: dict[str, Any] | None = None
    last_seen_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be empty")
        return normalized

    @field_validator("external_id", "provider", "region")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("attributes")
    @classmethod
    def validate_attributes_field(
        cls, value: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if value is None:
            return None
        return validate_asset_attributes(value)

    @field_validator("last_seen_at")
    @classmethod
    def validate_last_seen_at(cls, value: datetime | None) -> datetime | None:
        return _aware_timestamp(value)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> InfrastructureAssetUpdateRequest:
        for field_name in ("name", "asset_type", "status", "attributes"):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} cannot be null")
        return self


class InfrastructureAssetResponse(BaseModel):
    """Safe inventory fields returned to an authorized organization member."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    asset_type: AssetType
    external_id: str | None
    provider: str | None
    region: str | None
    status: AssetStatus
    attributes: dict[str, Any]
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime
