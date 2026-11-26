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
import app.routers.organizations as organizations_router
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


def _add_membership(
    engine,
    *,
    organization_id: str,
    user_id: str,
    role_id: str,
) -> str:
    with Session(engine) as db:
        membership = Membership(
            organization_id=UUID(organization_id),
            user_id=UUID(user_id),
            role_id=UUID(role_id),
        )
        db.add(membership)
        db.commit()
        return str(membership.id)


def _membership_id(engine, organization_id: str, user_id: str) -> str:
    with Session(engine) as db:
        membership_id = db.scalar(
            select(Membership.id)
            .where(Membership.organization_id == UUID(organization_id))
            .where(Membership.user_id == UUID(user_id))
        )
        assert membership_id is not None
        return str(membership_id)


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

    listed = test_client.get(f"/api/v1/organizations/{organization_id}/members")
    assert listed.status_code == 200
    members_by_user = {item["user_id"]: item for item in listed.json()}
    assert set(members_by_user) == {str(seeded["owner_id"]), target_id}
    assert members_by_user[target_id]["membership_id"] == payload["id"]
    assert members_by_user[target_id]["role_id"] == role_id


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

    path = f"/api/v1/organizations/{organization_id}/memberships"
    payload = {"user_id": target_id, "role_id": role_id}
    assert test_client.post(path, json=payload).status_code == 401

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


def test_owner_changes_member_role_and_audit_event_atomically(client) -> None:
    test_client, engine = client
    seeded = _seed_organization(
        engine,
        slug="membership-role-change",
        owner_email="membership-role-owner@example.com",
        target_email="membership-role-target@example.com",
    )
    organization_id = str(seeded["organization_id"])
    target_id = str(seeded["target_id"])
    member_role_id = str(seeded["roles"]["member"])
    viewer_role_id = str(seeded["roles"]["viewer"])
    membership_id = _add_membership(
        engine,
        organization_id=organization_id,
        user_id=target_id,
        role_id=member_role_id,
    )

    csrf_token = _login(test_client, "membership-role-owner@example.com")
    response = test_client.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{membership_id}",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={"role_id": viewer_role_id},
    )

    assert response.status_code == 200
    assert response.json()["id"] == membership_id
    assert response.json()["role_id"] == viewer_role_id
    repeated = test_client.patch(
        f"/api/v1/organizations/{organization_id}/memberships/{membership_id}",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={"role_id": viewer_role_id},
    )
    assert repeated.status_code == 200
    with Session(engine) as db:
        membership = db.get(Membership, UUID(membership_id))
        assert membership is not None
        assert str(membership.role_id) == viewer_role_id

    changed = [
        item
        for item in _audit_events(engine, organization_id)
        if item.event_type == "membership.role_changed"
    ]
    assert len(changed) == 1
    assert changed[0].target_id == membership_id
    assert changed[0].details == {
        "target_user_id": target_id,
        "previous_role_id": member_role_id,
        "previous_role_name": "member",
        "role_id": viewer_role_id,
        "role_name": "viewer",
    }


def test_last_active_owner_cannot_be_demoted_or_removed(client) -> None:
    test_client, engine = client
    seeded = _seed_organization(
        engine,
        slug="membership-last-owner",
        owner_email="membership-last-owner@example.com",
        target_email="membership-last-owner-target@example.com",
    )
    organization_id = str(seeded["organization_id"])
    owner_id = str(seeded["owner_id"])
    owner_membership_id = _membership_id(engine, organization_id, owner_id)
    csrf_token = _login(test_client, "membership-last-owner@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    path = (
        f"/api/v1/organizations/{organization_id}/memberships/" f"{owner_membership_id}"
    )

    demote = test_client.patch(
        path,
        headers=headers,
        json={"role_id": str(seeded["roles"]["member"])},
    )
    remove = test_client.delete(path, headers=headers)

    assert demote.status_code == 409
    assert remove.status_code == 409
    assert _membership_count(engine, organization_id, owner_id) == 1
    assert not [
        item
        for item in _audit_events(engine, organization_id)
        if item.event_type in {"membership.role_changed", "membership.deleted"}
    ]


def test_owner_can_remove_one_of_two_active_owners(client) -> None:
    test_client, engine = client
    seeded = _seed_organization(
        engine,
        slug="membership-two-owners",
        owner_email="membership-two-owner-a@example.com",
        target_email="membership-two-owner-b@example.com",
    )
    organization_id = str(seeded["organization_id"])
    target_id = str(seeded["target_id"])
    owner_role_id = str(seeded["roles"]["owner"])
    target_membership_id = _add_membership(
        engine,
        organization_id=organization_id,
        user_id=target_id,
        role_id=owner_role_id,
    )
    csrf_token = _login(test_client, "membership-two-owner-a@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    own_membership_id = _membership_id(engine, organization_id, str(seeded["owner_id"]))
    self_remove = test_client.delete(
        f"/api/v1/organizations/{organization_id}/memberships/{own_membership_id}",
        headers=headers,
    )
    assert self_remove.status_code == 409
    assert _membership_count(engine, organization_id, str(seeded["owner_id"])) == 1

    response = test_client.delete(
        f"/api/v1/organizations/{organization_id}/memberships/{target_membership_id}",
        headers=headers,
    )

    assert response.status_code == 204
    assert _membership_count(engine, organization_id, target_id) == 0
    deleted = [
        item
        for item in _audit_events(engine, organization_id)
        if item.event_type == "membership.deleted"
    ]
    assert len(deleted) == 1
    assert deleted[0].target_id == target_membership_id
    assert deleted[0].details == {
        "target_user_id": target_id,
        "role_id": owner_role_id,
        "role_name": "owner",
    }


def test_membership_lifecycle_enforces_permission_csrf_and_tenant_scope(client) -> None:
    test_client, engine = client
    tenant_a = _seed_organization(
        engine,
        slug="membership-lifecycle-tenant-a",
        owner_email="membership-lifecycle-owner-a@example.com",
        target_email="membership-lifecycle-target-a@example.com",
    )
    tenant_b = _seed_organization(
        engine,
        slug="membership-lifecycle-tenant-b",
        owner_email="membership-lifecycle-owner-b@example.com",
        target_email="membership-lifecycle-target-b@example.com",
    )
    organization_a = str(tenant_a["organization_id"])
    target_a = str(tenant_a["target_id"])
    target_membership_a = _add_membership(
        engine,
        organization_id=organization_a,
        user_id=target_a,
        role_id=str(tenant_a["roles"]["member"]),
    )
    foreign_membership = _add_membership(
        engine,
        organization_id=str(tenant_b["organization_id"]),
        user_id=str(tenant_b["target_id"]),
        role_id=str(tenant_b["roles"]["member"]),
    )

    with Session(engine) as db:
        viewer = User(
            email="membership-lifecycle-viewer@example.com",
            display_name="Membership lifecycle viewer",
            password_hash=hash_password(PASSWORD),
        )
        db.add(viewer)
        db.flush()
        viewer_role = db.scalar(
            select(Role)
            .where(Role.organization_id == UUID(organization_a))
            .where(Role.name == "viewer")
        )
        assert viewer_role is not None
        db.add(
            Membership(
                organization_id=UUID(organization_a),
                user_id=viewer.id,
                role_id=viewer_role.id,
            )
        )
        db.commit()

    path = (
        f"/api/v1/organizations/{organization_a}/memberships/" f"{target_membership_a}"
    )
    viewer_csrf = _login(test_client, "membership-lifecycle-viewer@example.com")
    viewer_headers = {"Origin": ORIGIN, "X-CSRF-Token": viewer_csrf}
    assert (
        test_client.patch(
            path,
            headers=viewer_headers,
            json={"role_id": str(tenant_a["roles"]["viewer"])},
        ).status_code
        == 403
    )
    assert test_client.delete(path, headers=viewer_headers).status_code == 403
    assert (
        test_client.post(
            "/api/v1/auth/logout",
            headers=viewer_headers,
        ).status_code
        == 204
    )

    owner_csrf = _login(test_client, "membership-lifecycle-owner-a@example.com")
    owner_headers = {"Origin": ORIGIN, "X-CSRF-Token": owner_csrf}
    assert (
        test_client.patch(
            path,
            headers={"Origin": "https://attacker.example", "X-CSRF-Token": owner_csrf},
            json={"role_id": str(tenant_a["roles"]["viewer"])},
        ).status_code
        == 403
    )
    assert (
        test_client.delete(
            path,
            headers={"Origin": ORIGIN, "X-CSRF-Token": "forged"},
        ).status_code
        == 403
    )

    foreign_path = (
        f"/api/v1/organizations/{organization_a}/memberships/" f"{foreign_membership}"
    )
    assert (
        test_client.patch(
            foreign_path,
            headers=owner_headers,
            json={"role_id": str(tenant_a["roles"]["viewer"])},
        ).status_code
        == 404
    )
    assert test_client.delete(foreign_path, headers=owner_headers).status_code == 404
    foreign_role_change = test_client.patch(
        path,
        headers=owner_headers,
        json={"role_id": str(tenant_b["roles"]["viewer"])},
    )
    assert foreign_role_change.status_code == 404
    assert _membership_count(engine, organization_a, target_a) == 1
    assert (
        _membership_count(
            engine, str(tenant_b["organization_id"]), str(tenant_b["target_id"])
        )
        == 1
    )


def test_membership_role_change_rolls_back_when_audit_write_fails(
    client, monkeypatch
) -> None:
    test_client, engine = client
    seeded = _seed_organization(
        engine,
        slug="membership-audit-rollback",
        owner_email="membership-audit-rollback-owner@example.com",
        target_email="membership-audit-rollback-target@example.com",
    )
    organization_id = str(seeded["organization_id"])
    target_id = str(seeded["target_id"])
    member_role_id = str(seeded["roles"]["member"])
    viewer_role_id = str(seeded["roles"]["viewer"])
    membership_id = _add_membership(
        engine,
        organization_id=organization_id,
        user_id=target_id,
        role_id=member_role_id,
    )
    csrf_token = _login(test_client, "membership-audit-rollback-owner@example.com")

    def fail_audit_write(*_args, **_kwargs):
        raise RuntimeError("audit writer unavailable")

    monkeypatch.setattr(organizations_router, "record_audit_event", fail_audit_write)
    with pytest.raises(RuntimeError, match="audit writer unavailable"):
        test_client.patch(
            f"/api/v1/organizations/{organization_id}/memberships/{membership_id}",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
            json={"role_id": viewer_role_id},
        )

    with Session(engine) as db:
        membership = db.get(Membership, UUID(membership_id))
        assert membership is not None
        assert str(membership.role_id) == member_role_id
    assert not [
        item
        for item in _audit_events(engine, organization_id)
        if item.event_type == "membership.role_changed"
    ]
