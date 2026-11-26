"""Authentication-to-audit integration tests (P1-A5)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
import app.routers.auth as auth_router
from app.models.audit import AuditEvent
from app.models.identity import Membership, Organization, User
from app.models.sessions import AuthSession
from app.services.passwords import hash_password
from app.services.rbac import create_default_roles_for_organization

ORIGIN = "http://localhost:3000"
PASSWORD = "correct-horse-battery"


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

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
    monkeypatch.setattr(
        auth_router, "_enforce_login_rate_limit", lambda _request, _email: None
    )
    with TestClient(app) as test_client:
        yield test_client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def _seed_user(
    engine,
    *,
    email: str,
    organization_slugs: tuple[str, ...] = (),
    deleted_organization_slugs: tuple[str, ...] = (),
) -> tuple[str, dict[str, str]]:
    with Session(engine) as db:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()

        organizations: dict[str, str] = {}
        for slug in (*organization_slugs, *deleted_organization_slugs):
            organization = Organization(
                name=slug.title(),
                slug=slug,
                deleted_at=(
                    datetime.now(timezone.utc)
                    if slug in deleted_organization_slugs
                    else None
                ),
            )
            db.add(organization)
            db.flush()
            roles = create_default_roles_for_organization(db, organization.id)
            owner_role = next(role for role in roles if role.name == "owner")
            db.add(
                Membership(
                    organization_id=organization.id,
                    user_id=user.id,
                    role_id=owner_role.id,
                )
            )
            organizations[slug] = str(organization.id)

        user_id = str(user.id)
        db.commit()
        return user_id, organizations


def _events(engine) -> list[AuditEvent]:
    with Session(engine) as db:
        return list(
            db.scalars(
                select(AuditEvent).order_by(
                    AuditEvent.occurred_at, AuditEvent.id
                )
            ).all()
        )


def _login(client: TestClient, email: str):
    return client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )


def test_successful_session_lifecycle_is_audited_per_active_tenant(client) -> None:
    test_client, engine = client
    user_id, organizations = _seed_user(
        engine,
        email="multi-tenant@example.com",
        organization_slugs=("auth-tenant-a", "auth-tenant-b"),
        deleted_organization_slugs=("auth-tenant-deleted",),
    )

    login = _login(test_client, "multi-tenant@example.com")
    assert login.status_code == 200
    csrf_token = login.json()["csrf_token"]

    with Session(engine) as db:
        session = db.scalar(
            select(AuthSession).where(AuthSession.user_id == UUID(user_id))
        )
        assert session is not None
        session_id = str(session.id)

    created_events = [
        item for item in _events(engine) if item.event_type == "auth.session.created"
    ]
    active_organization_ids = {
        organizations["auth-tenant-a"],
        organizations["auth-tenant-b"],
    }
    assert {str(item.organization_id) for item in created_events} == (
        active_organization_ids
    )
    assert all(str(item.actor_user_id) == user_id for item in created_events)
    assert all(item.target_type == "auth_session" for item in created_events)
    assert all(item.target_id == session_id for item in created_events)
    assert all(item.details == {"method": "local_password"} for item in created_events)

    logout = test_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
    )
    assert logout.status_code == 204

    all_events = _events(engine)
    revoked_events = [
        item for item in all_events if item.event_type == "auth.session.revoked"
    ]
    assert {str(item.organization_id) for item in revoked_events} == (
        active_organization_ids
    )
    assert all(item.target_id == session_id for item in revoked_events)

    with Session(engine) as db:
        revoked_session = db.get(AuthSession, UUID(session_id))
        assert revoked_session is not None
        assert revoked_session.revoked_at is not None


def test_failed_login_and_invalid_csrf_do_not_emit_success_events(client) -> None:
    test_client, engine = client
    _seed_user(
        engine,
        email="auth-negative@example.com",
        organization_slugs=("auth-negative",),
    )

    wrong_password = test_client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "auth-negative@example.com", "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401
    assert _events(engine) == []

    untrusted_origin = test_client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"email": "auth-negative@example.com", "password": PASSWORD},
    )
    assert untrusted_origin.status_code == 403
    assert _events(engine) == []

    login = _login(test_client, "auth-negative@example.com")
    assert login.status_code == 200
    assert [
        item.event_type for item in _events(engine)
    ] == ["auth.session.created"]

    invalid_csrf = test_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": "forged"},
    )
    assert invalid_csrf.status_code == 403
    assert [
        item.event_type for item in _events(engine)
    ] == ["auth.session.created"]

    valid_logout = test_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert valid_logout.status_code == 204
    assert sorted(item.event_type for item in _events(engine)) == [
        "auth.session.created",
        "auth.session.revoked",
    ]


def test_user_without_membership_can_authenticate_without_tenant_audit(client) -> None:
    test_client, engine = client
    _seed_user(engine, email="no-tenant@example.com")

    login = _login(test_client, "no-tenant@example.com")
    assert login.status_code == 200
    assert test_client.get("/api/v1/auth/me").status_code == 200

    logout = test_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert logout.status_code == 204
    assert _events(engine) == []
