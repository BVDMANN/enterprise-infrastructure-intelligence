"""Enterprise Infrastructure Intelligence — API entrypoint.

FastAPI application skeleton (PHASE 0). Only health endpoints exist so far;
business modules arrive in PHASE 1.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import health

app = FastAPI(
    title="Enterprise Infrastructure Intelligence API",
    version="0.1.0",
    description="Control Plane API — see docs/api/API_SPECIFICATION.md",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)


@app.get("/health", tags=["health"])
async def health_root() -> dict[str, str]:
    """Liveness probe (no auth, no database)."""
    return {"status": "ok"}
