"""Audit event service and HTTP tests (P1-A5)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
import app.routers.auth as auth_router
from app.models.identity import Membership, Organization, User
from app.models.rbac import Role
from app.services.audit import list_audit_events, record_audit_event
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


def _seed_membership(
    engine,
    *,
    slug: str,
    email: str,
    role_name: str,
) -> tuple[str, str]:
    with Session(engine) as db:
        organization = Organization(name=slug.title(), slug=slug)
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(PASSWORD),
        )
        db.add_all([organization, user])
        db.flush()
        roles = create_default_roles_for_organization(db, organization.id)
        db.flush()
        role = next(item for item in roles if item.name == role_name)
        db.add(
            Membership(
                organization_id=organization.id,
                user_id=user.id,
                role_id=role.id,
            )
        )
        db.commit()
        return str(organization.id), str(user.id)


def _add_member(engine, organization_id: str, email: str, role_name: str) -> str:
    with Session(engine) as db:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        role = (
            db.query(Role)
            .filter_by(organization_id=UUID(organization_id), name=role_name)
            .one()
        )
        db.add(
            Membership(
                organization_id=UUID(organization_id),
                user_id=user.id,
                role_id=role.id,
            )
        )
        db.commit()
        return str(user.id)


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_audit_service_is_tenant_scoped_and_newest_first(client) -> None:
    _test_client, engine = client
    organization_a, actor_a = _seed_membership(
        engine, slug="audit-a", email="owner-a@example.com", role_name="owner"
    )
    organization_b, actor_b = _seed_membership(
        engine, slug="audit-b", email="owner-b@example.com", role_name="owner"
    )

    with Session(engine) as db:
        older = record_audit_event(
            db,
            organization_id=UUID(organization_a),
            actor_user_id=UUID(actor_a),
            event_type="organization.viewed",
            occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            details={"source": "api"},
        )
        newer = record_audit_event(
            db,
            organization_id=UUID(organization_a),
            actor_user_id=UUID(actor_a),
            event_type="member.invited",
            occurred_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            target_type="membership",
            target_id="membership-123",
            request_id="request-123",
        )
        other = record_audit_event(
            db,
            organization_id=UUID(organization_b),
            actor_user_id=UUID(actor_b),
            event_type="organization.viewed",
        )
        db.commit()

        first_page = list_audit_events(
            db, UUID(organization_a), limit=1
        )
        all_a = list_audit_events(db, UUID(organization_a), limit=100)
        all_b = list_audit_events(db, UUID(organization_b))

    assert [item.id for item in first_page] == [newer.id]
    assert {item.id for item in all_a} == {older.id, newer.id}
    assert [item.id for item in all_b] == [other.id]
    assert all(item.organization_id == UUID(organization_a) for item in all_a)


def test_audit_service_rejects_foreign_actor_and_sensitive_details(client) -> None:
    _test_client, engine = client
    organization_a, actor_a = _seed_membership(
        engine, slug="audit-a", email="owner-a@example.com", role_name="owner"
    )
    organization_b, _actor_b = _seed_membership(
        engine, slug="audit-b", email="owner-b@example.com", role_name="owner"
    )

    with Session(engine) as db:
        with pytest.raises(ValueError, match="active member"):
            record_audit_event(
                db,
                organization_id=UUID(organization_b),
                actor_user_id=UUID(actor_a),
                event_type="member.updated",
            )
        with pytest.raises(ValueError, match="credentials or secrets"):
            record_audit_event(
                db,
                organization_id=UUID(organization_a),
                actor_user_id=UUID(actor_a),
                event_type="member.updated",
                details={"nested": {"access_token": "must-not-be-stored"}},
            )
        with pytest.raises(ValueError, match="JSON object"):
            record_audit_event(
                db,
                organization_id=UUID(organization_a),
                actor_user_id=UUID(actor_a),
                event_type="member.updated",
                details=["not", "an", "object"],
            )
        with pytest.raises(ValueError, match="event_type"):
            record_audit_event(
                db,
                organization_id=UUID(organization_a),
                actor_user_id=UUID(actor_a),
                event_type="  ",
            )


def test_audit_events_http_endpoint_enforces_session_tenant_and_permission(
    client,
) -> None:
    test_client, engine = client
    organization_a, owner_a = _seed_membership(
        engine, slug="audit-http-a", email="audit-owner@example.com", role_name="owner"
    )
    organization_b, _owner_b = _seed_membership(
        engine, slug="audit-http-b", email="other-owner@example.com", role_name="owner"
    )
    _add_member(engine, organization_a, "audit-member@example.com", "member")

    with Session(engine) as db:
        stored = record_audit_event(
            db,
            organization_id=UUID(organization_a),
            actor_user_id=UUID(owner_a),
            event_type="organization.updated",
            details={"field": "display_name"},
        )
        db.commit()

    path = f"/api/v1/organizations/{organization_a}/audit-events"
    assert test_client.get(path).status_code == 401

    csrf = _login(test_client, "audit-owner@example.com")
    response = test_client.get(path)
    assert response.status_code == 200
    assert response.json()[0]["id"] == str(stored.id)
    assert response.json()[0]["details"] == {"field": "display_name"}
    assert test_client.get(
        f"/api/v1/organizations/{organization_b}/audit-events"
    ).status_code == 404
    assert test_client.get(f"{path}?limit=101").status_code == 422

    logout = test_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
    )
    assert logout.status_code == 204

    _login(test_client, "audit-member@example.com")
    assert test_client.get(path).status_code == 403
