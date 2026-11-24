"""Health router (PHASE 0 skeleton — the only routes that exist so far)."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
async def health_v1() -> dict[str, str]:
    """Versioned health endpoint (no auth, no database)."""
    return {"status": "ok", "api_version": "v1"}
