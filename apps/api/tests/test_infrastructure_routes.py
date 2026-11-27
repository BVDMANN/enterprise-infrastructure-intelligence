"""Tenant-scoped infrastructure asset API integration tests (P1-A6.1)."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
import app.routers.auth as auth_router
import app.routers.infrastructure as infrastructure_router
from app.models.audit import AuditEvent
from app.models.identity import Membership, Organization, User
from app.models.infrastructure import InfrastructureAsset
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


def _seed_membership(
    engine,
    *,
    slug: str,
    email: str,
    role_name: str = "owner",
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


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _asset_count(engine, organization_id: str) -> int:
    with Session(engine) as db:
        return len(
            db.scalars(
                select(InfrastructureAsset.id).where(
                    InfrastructureAsset.organization_id == UUID(organization_id)
                )
            ).all()
        )


def test_owner_can_create_list_update_and_soft_delete_assets(client) -> None:
    test_client, engine = client
    organization_id, owner_id = _seed_membership(
        engine,
        slug="infrastructure-lifecycle",
        email="infrastructure-owner@example.com",
    )
    csrf_token = _login(test_client, "infrastructure-owner@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    collection = f"/api/v1/organizations/{organization_id}/infrastructure/assets"

    created = test_client.post(
        collection,
        headers=headers,
        json={
            "name": "Production database",
            "asset_type": "database",
            "external_id": "prod-db-01",
            "provider": "aws",
            "region": "eu-west-3",
            "status": "healthy",
            "attributes": {"environment": "production", "team": "platform"},
        },
    )
    assert created.status_code == 201
    asset = created.json()
    assert asset["organization_id"] == organization_id
    assert asset["name"] == "Production database"
    assert asset["status"] == "healthy"
    assert asset["attributes"]["environment"] == "production"
    asset_id = asset["id"]

    listed = test_client.get(collection)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [asset_id]

    filtered = test_client.get(f"{collection}?status=healthy&asset_type=database")
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert test_client.get(f"{collection}?status=offline").json() == []

    detail_path = f"{collection}/{asset_id}"
    detail = test_client.get(detail_path)
    assert detail.status_code == 200
    assert detail.json()["external_id"] == "prod-db-01"

    updated = test_client.patch(
        detail_path,
        headers=headers,
        json={
            "status": "degraded",
            "attributes": {"environment": "production", "team": "platform"},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "degraded"

    deleted = test_client.delete(detail_path, headers=headers)
    assert deleted.status_code == 204
    assert test_client.get(collection).json() == []
    assert test_client.get(detail_path).status_code == 404
    assert _asset_count(engine, organization_id) == 1

    with Session(engine) as db:
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == UUID(organization_id))
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            ).all()
        )
    asset_events = [
        item for item in events if item.event_type.startswith("infrastructure.asset.")
    ]
    assert len(asset_events) == 3
    assert {item.event_type for item in asset_events} == {
        "infrastructure.asset.created",
        "infrastructure.asset.updated",
        "infrastructure.asset.deleted",
    }
    assert all(str(item.actor_user_id) == owner_id for item in asset_events)
    assert all(item.target_id == asset_id for item in asset_events)
    updated_event = next(
        item
        for item in asset_events
        if item.event_type == "infrastructure.asset.updated"
    )
    assert updated_event.details == {"changed_fields": ["attributes", "status"]}


def test_infrastructure_assets_are_hidden_across_tenants(client) -> None:
    test_client, engine = client
    organization_a, _ = _seed_membership(
        engine,
        slug="infrastructure-tenant-a",
        email="infrastructure-owner-a@example.com",
    )
    organization_b, _ = _seed_membership(
        engine,
        slug="infrastructure-tenant-b",
        email="infrastructure-owner-b@example.com",
    )
    with Session(engine) as db:
        foreign_asset = InfrastructureAsset(
            organization_id=UUID(organization_b),
            name="Tenant B server",
            asset_type="server",
            external_id="tenant-b-server-01",
            status="healthy",
        )
        db.add(foreign_asset)
        db.commit()
        foreign_asset_id = str(foreign_asset.id)

    _login(test_client, "infrastructure-owner-a@example.com")
    foreign_collection = f"/api/v1/organizations/{organization_b}/infrastructure/assets"
    own_collection = f"/api/v1/organizations/{organization_a}/infrastructure/assets"
    assert test_client.get(foreign_collection).status_code == 404
    assert test_client.get(f"{own_collection}/{foreign_asset_id}").status_code == 404


def test_viewer_can_read_assets_but_cannot_manage_them(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine,
        slug="infrastructure-viewer",
        email="infrastructure-viewer-owner@example.com",
    )
    with Session(engine) as db:
        viewer = User(
            email="infrastructure-viewer@example.com",
            display_name="Infrastructure viewer",
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

    _login(test_client, "infrastructure-viewer@example.com")
    collection = f"/api/v1/organizations/{organization_id}/infrastructure/assets"
    assert test_client.get(collection).status_code == 200
    denied = test_client.post(
        collection,
        headers={"Origin": ORIGIN, "X-CSRF-Token": "not-used-forbidden-user"},
        json={"name": "Forbidden", "asset_type": "server"},
    )
    assert denied.status_code == 403


def test_asset_writes_require_session_csrf_and_reject_sensitive_attributes(
    client,
) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine,
        slug="infrastructure-csrf",
        email="infrastructure-csrf-owner@example.com",
    )
    collection = f"/api/v1/organizations/{organization_id}/infrastructure/assets"
    payload = {"name": "API server", "asset_type": "server"}
    assert test_client.post(collection, json=payload).status_code == 401

    csrf_token = _login(test_client, "infrastructure-csrf-owner@example.com")
    assert (
        test_client.post(
            collection,
            headers={"Origin": ORIGIN},
            json=payload,
        ).status_code
        == 403
    )
    assert (
        test_client.post(
            collection,
            headers={"Origin": "https://attacker.example", "X-CSRF-Token": csrf_token},
            json=payload,
        ).status_code
        == 403
    )
    secret = test_client.post(
        collection,
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={
            "name": "API server",
            "asset_type": "server",
            "attributes": {"nested": [{"api_key": "must-not-be-stored"}]},
        },
    )
    assert secret.status_code == 422
    access_key = test_client.post(
        collection,
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={
            "name": "API server",
            "asset_type": "server",
            "attributes": {"access_key": "must-not-be-stored"},
        },
    )
    assert access_key.status_code == 422
    oversized = test_client.post(
        collection,
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={
            "name": "API server",
            "asset_type": "server",
            "attributes": {"description": "x" * (16 * 1024)},
        },
    )
    assert oversized.status_code == 422
    naive_timestamp = test_client.post(
        collection,
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={
            "name": "API server",
            "asset_type": "server",
            "last_seen_at": "2026-11-27T12:00:00",
        },
    )
    assert naive_timestamp.status_code == 422
    assert _asset_count(engine, organization_id) == 0


def test_duplicate_external_id_and_invalid_asset_type_are_rejected(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine,
        slug="infrastructure-unique",
        email="infrastructure-unique-owner@example.com",
    )
    csrf_token = _login(test_client, "infrastructure-unique-owner@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    collection = f"/api/v1/organizations/{organization_id}/infrastructure/assets"
    payload = {
        "name": "Application server",
        "asset_type": "server",
        "external_id": "app-server-01",
    }
    assert (
        test_client.post(collection, headers=headers, json=payload).status_code == 201
    )
    duplicate = test_client.post(collection, headers=headers, json=payload)
    assert duplicate.status_code == 409
    invalid_type = test_client.post(
        collection,
        headers=headers,
        json={"name": "Unsupported", "asset_type": "firewall"},
    )
    assert invalid_type.status_code == 422
    assert _asset_count(engine, organization_id) == 1


def test_asset_creation_rolls_back_when_audit_write_fails(client, monkeypatch) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine,
        slug="infrastructure-audit-rollback",
        email="infrastructure-audit-owner@example.com",
    )
    csrf_token = _login(test_client, "infrastructure-audit-owner@example.com")

    def fail_audit_write(*_args, **_kwargs):
        raise RuntimeError("audit writer unavailable")

    monkeypatch.setattr(infrastructure_router, "record_audit_event", fail_audit_write)
    with pytest.raises(RuntimeError, match="audit writer unavailable"):
        test_client.post(
            f"/api/v1/organizations/{organization_id}/infrastructure/assets",
            headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
            json={"name": "Rollback asset", "asset_type": "server"},
        )
    assert _asset_count(engine, organization_id) == 0
