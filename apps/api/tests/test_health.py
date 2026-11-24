"""API tests (PHASE 0)."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_root() -> None:
    """GET /health returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_v1() -> None:
    """GET /api/v1/health returns ok with the API version."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["api_version"] == "v1"


def test_unknown_route_returns_404() -> None:
    """Unknown routes return a 404 without leaking internals."""
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
