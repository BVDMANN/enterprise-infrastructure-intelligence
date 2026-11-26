"""Tenant-scoped membership mutation and audit integration tests (P1-A5.2)."""

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
from app.models.rbac import Role
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


def _seed_organization(
    engine,
    *,
    slug: str,
    owner_email: str,
    target_email: str,
    owner_role: str = "owner",
    target_active: bool = True,
    target_deleted: bool = False,
) -> dict[str, object]:
    with Session(engine) as db:
        organization = Organization(name=slug.title(), slug=slug)
        owner = User(
            email=owner_email,
            display_name=owner_email.split("@")[0],
            password_hash=hash_password(PASSWORD),
        )
        target = User(
            email=target_email,
            display_name=target_email.split("@")[0],
            is_active=target_active,
            deleted_at=datetime.now(timezone.utc) if target_deleted else None,
        )
        db.add_all([organization, owner, target])
        db.flush()

        roles = create_default_roles_for_organization(db, organization.id)
        role_by_name = {role.name: role for role in roles}
        db.add(
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role_id=role_by_name[owner_role].id,
            )
        )
        result = {
            "organization_id": str(organization.id),
            "owner_id": str(owner.id),
            "target_id": str(target.id),
            "roles": {name: str(role.id) for name, role in role_by_name.items()},
        }
        db.commit()
        return result


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _membership_count(engine, organization_id: str, user_id: str) -> int:
    with Session(engine) as db:
        return len(
            db.scalars(
                select(Membership.id)
                .where(Membership.organization_id == UUID(organization_id))
                .where(Membership.user_id == UUID(user_id))
            ).all()
        )


def _audit_events(engine, organization_id: str) -> list[AuditEvent]:
    with Session(engine) as db:
        return list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == UUID(organization_id))
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            ).all()
        )


def test_owner_adds_existing_member_and_audit_event_atomically(client) -> None:
    test_client, engine = client
    seeded = _seed_organization(
        engine,
        slug="membership-create",
        owner_email="membership-owner@example.com",
        target_email="existing-user@example.com",
    )
    organization_id = str(seeded["organization_id"])
    target_id = str(seeded["target_id"])
    role_id = str(seeded["roles"]["member"])

    csrf_token = _login(test_client, "membership-owner@example.com")
    response = test_client.post(
        f"/api/v1/organizations/{organization_id}/memberships",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={"user_id": target_id, "role_id": role_id},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["user_id"] == target_id
    assert payload["role_id"] == role_id
    assert payload["id"]
    assert payload["created_at"]
    assert _membership_count(engine, organization_id, target_id) == 1

    events = _audit_events(engine, organization_id)
    created = [item for item in events if item.event_type == "membership.created"]
    assert len(created) == 1
    assert str(created[0].actor_user_id) == str(seeded["owner_id"])
    assert created[0].target_type == "membership"
    assert created[0].target_id == payload["id"]
    assert created[0].details == {
        "target_user_id": target_id,
        "role_id": role_id,
        "role_name": "member",
    }

    listed = test_client.get(
        f"/api/v1/organizations/{organization_id}/members"
    )
    assert listed.status_code == 200
    assert {item["user_id"] for item in listed.json()} == {
        str(seeded["owner_id"]),
        target_id,
    }


def test_membership_mutation_requires_owner_permission_and_session_csrf(client) -> None:
    test_client, engine = client
    seeded = _seed_organization(
        engine,
        slug="membership-security",
        owner_email="membership-owner-security@example.com",
        target_email="security-target@example.com",
    )
    organization_id = str(seeded["organization_id"])
    target_id = str(seeded["target_id"])
    role_id = str(seeded["roles"]["member"])

    with Session(engine) as db:
        viewer = User(
            email="membership-viewer@example.com",
            display_name="Membership viewer",
            password_hash=hash_password(PASSWORD),
        )
        db.add(viewer)
        db.flush()
        viewer_role = db.scalar(
            select(Role)
            .where(Role.organization_id == UUID(organization_id))
            .where(Role.name == "viewer")
        )
        assert viewer_role is not None
        db.add(
            Membership(
                organization_id=UUID(organization_id),
                user_id=viewer.id,
                role_id=viewer_role.id,
            )
        )
        db.commit()

    path = f"/api/v1/organizations/{organization_id}/memberships"
    payload = {"user_id": target_id, "role_id": role_id}
    assert test_client.post(path, json=payload).status_code == 401

    viewer_csrf = _login(test_client, "membership-viewer@example.com")
    forbidden = test_client.post(
        path,
        headers={"Origin": ORIGIN, "X-CSRF-Token": viewer_csrf},
        json=payload,
    )
    assert forbidden.status_code == 403
    assert _membership_count(engine, organization_id, target_id) == 0

    viewer_logout = test_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": viewer_csrf},
    )
    assert viewer_logout.status_code == 204

    owner_csrf = _login(test_client, "membership-owner-security@example.com")
    invalid_origin = test_client.post(
        path,
        headers={
            "Origin": "https://attacker.example",
            "X-CSRF-Token": owner_csrf,
        },
        json=payload,
    )
    assert invalid_origin.status_code == 403

    invalid_csrf = test_client.post(
        path,
        headers={"Origin": ORIGIN, "X-CSRF-Token": "forged"},
        json=payload,
    )
    assert invalid_csrf.status_code == 403
    assert _membership_count(engine, organization_id, target_id) == 0
    assert not [
        item
        for item in _audit_events(engine, organization_id)
        if item.event_type == "membership.created"
    ]


def test_membership_mutation_rejects_foreign_role_inactive_user_and_duplicates(
    client,
) -> None:
    test_client, engine = client
    tenant_a = _seed_organization(
        engine,
        slug="membership-tenant-a",
        owner_email="membership-owner-a@example.com",
        target_email="membership-target-a@example.com",
    )
    tenant_b = _seed_organization(
        engine,
        slug="membership-tenant-b",
        owner_email="membership-owner-b@example.com",
        target_email="membership-target-b@example.com",
    )
    organization_id = str(tenant_a["organization_id"])
    target_id = str(tenant_a["target_id"])
    csrf_token = _login(test_client, "membership-owner-a@example.com")
    path = f"/api/v1/organizations/{organization_id}/memberships"
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}

    foreign_role = test_client.post(
        path,
        headers=headers,
        json={
            "user_id": target_id,
            "role_id": str(tenant_b["roles"]["member"]),
        },
    )
    assert foreign_role.status_code == 404
    assert _membership_count(engine, organization_id, target_id) == 0

    with Session(engine) as db:
        inactive = User(
            email="inactive-target@example.com",
            display_name="Inactive target",
            is_active=False,
        )
        deleted = User(
            email="deleted-target@example.com",
            display_name="Deleted target",
            deleted_at=datetime.now(timezone.utc),
        )
        db.add_all([inactive, deleted])
        db.commit()
        inactive_id = str(inactive.id)
        deleted_id = str(deleted.id)

    for user_id in (inactive_id, deleted_id):
        response = test_client.post(
            path,
            headers=headers,
            json={
                "user_id": user_id,
                "role_id": str(tenant_a["roles"]["member"]),
            },
        )
        assert response.status_code == 404
        assert _membership_count(engine, organization_id, user_id) == 0

    create = test_client.post(
        path,
        headers=headers,
        json={
            "user_id": target_id,
            "role_id": str(tenant_a["roles"]["member"]),
        },
    )
    assert create.status_code == 201

    duplicate = test_client.post(
        path,
        headers=headers,
        json={
            "user_id": target_id,
            "role_id": str(tenant_a["roles"]["member"]),
        },
    )
    assert duplicate.status_code == 409
    assert _membership_count(engine, organization_id, target_id) == 1
    created_events = [
        item
        for item in _audit_events(engine, organization_id)
        if item.event_type == "membership.created"
    ]
    assert len(created_events) == 1
