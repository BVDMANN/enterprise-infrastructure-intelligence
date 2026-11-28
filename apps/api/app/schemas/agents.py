"""Safe API schemas for infrastructure agent credential management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentCredentialCreateRequest(BaseModel):
    """Create one asset-scoped agent credential with a bounded lifetime."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    expires_in_days: int = Field(default=90, ge=1, le=365)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized


class AgentCredentialResponse(BaseModel):
    """Credential metadata; never exposes the digest or plaintext token."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    asset_id: UUID
    created_by_user_id: UUID
    name: str
    token_prefix: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class AgentCredentialCreateResponse(AgentCredentialResponse):
    """The plaintext token is returned exactly once, at creation."""

    token: str
