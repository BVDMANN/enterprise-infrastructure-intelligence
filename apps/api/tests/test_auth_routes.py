"""HTTP authentication route tests (P1-A2.2)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.session import Base, get_db
from app.main import app
from app.models.identity import User
from app.services.passwords import hash_password

ORIGIN = "http://localhost:3000"


@pytest.fixture()
def client():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):  # noqa: ANN001, ANN202
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)

    def override_get_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def _create_user(client: TestClient, *, active: bool = True, deleted: bool = False) -> None:
    dependency = app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        db.add(
            User(
                email="admin@example.com",
                display_name="EII Admin",
                password_hash=hash_password("correct-horse-battery"),
                is_active=active,
                deleted_at=datetime.now(timezone.utc) if deleted else None,
            )
        )
        db.commit()
    finally:
        dependency.close()


def test_login_me_and_logout_round_trip(client: TestClient) -> None:
    _create_user(client)
    login = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "ADMIN@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["user"]["email"] == "admin@example.com"
    assert payload["csrf_token"]
    cookie = login.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api/v1/auth" in cookie
    assert "secure" not in cookie

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == payload["user"]["id"]

    logout = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": payload["csrf_token"]},
    )
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rejects_invalid_credentials_without_enumeration(client: TestClient) -> None:
    _create_user(client)
    wrong = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "admin@example.com", "password": "wrong-password"},
    )
    missing = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "missing@example.com", "password": "wrong-password"},
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["detail"] == missing.json()["detail"]


def test_login_rejects_untrusted_origin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"email": "admin@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 403


def test_logout_requires_session_bound_csrf(client: TestClient) -> None:
    _create_user(client)
    client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "admin@example.com", "password": "correct-horse-battery"},
    )
    response = client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": "forged"},
    )
    assert response.status_code == 403
    assert client.get("/api/v1/auth/me").status_code == 200
