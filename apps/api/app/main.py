"""Enterprise Infrastructure Intelligence — API entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import (
    agent_ingestion,
    agents,
    auth,
    health,
    infrastructure,
    invitations,
    organizations,
)

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
app.include_router(auth.router)
app.include_router(organizations.router)
app.include_router(infrastructure.router)
app.include_router(invitations.router)
app.include_router(agents.router)
app.include_router(agent_ingestion.router)


@app.get("/health", tags=["health"])
async def health_root() -> dict[str, str]:
    """Liveness probe (no auth, no database)."""
    return {"status": "ok"}
