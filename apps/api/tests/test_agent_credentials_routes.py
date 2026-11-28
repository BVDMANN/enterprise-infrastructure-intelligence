"""Tenant-scoped infrastructure agent credential API tests (P1-A7.1)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
import app.routers.auth as auth_router
from app.models.agents import InfrastructureAgentCredential
from app.models.audit import AuditEvent
from app.models.identity import Membership, Organization, User
from app.models.infrastructure import InfrastructureAsset
from app.models.rbac import Role
from app.services.agents import (
    authenticate_agent_credential,
    create_agent_credential,
)
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


def _seed_asset(
    engine,
    *,
    slug: str,
    email: str,
) -> tuple[str, str, str]:
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
        owner_role = next(role for role in roles if role.name == "owner")
        db.add(
            Membership(
                organization_id=organization.id,
                user_id=user.id,
                role_id=owner_role.id,
            )
        )
        asset = InfrastructureAsset(
            organization_id=organization.id,
            name=f"{slug} server",
            asset_type="server",
            external_id=f"{slug}-server-01",
            status="healthy",
        )
        db.add(asset)
        db.commit()
        return str(organization.id), str(user.id), str(asset.id)


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _agent_collection(organization_id: str, asset_id: str) -> str:
    return (
        f"/api/v1/organizations/{organization_id}/infrastructure/assets/"
        f"{asset_id}/agents"
    )


def test_owner_can_issue_list_revoke_and_authenticate_agent(client) -> None:
    test_client, engine = client
    organization_id, user_id, asset_id = _seed_asset(
        engine,
        slug="agent-lifecycle",
        email="agent-owner@example.com",
    )
    csrf_token = _login(test_client, "agent-owner@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    collection = _agent_collection(organization_id, asset_id)

    created = test_client.post(
        collection,
        headers=headers,
        json={"name": "proxmox-node-01", "expires_in_days": 30},
    )
    assert created.status_code == 201
    body = created.json()
    token = body["token"]
    assert token.startswith("eii_agent_")
    assert body["name"] == "proxmox-node-01"
    assert body["created_by_user_id"] == user_id
    assert "token_hash" not in body
    assert "credential_hash" not in body

    with Session(engine) as db:
        credential = db.scalar(
            select(InfrastructureAgentCredential).where(
                InfrastructureAgentCredential.id == UUID(body["id"])
            )
        )
        assert credential is not None
        assert credential.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert credential.token_prefix == token[:20]
        assert authenticate_agent_credential(db, token) is not None
        assert authenticate_agent_credential(db, "eii_agent_invalid") is None

    listed = test_client.get(collection)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    listed_item = listed.json()[0]
    assert listed_item["id"] == body["id"]
    assert listed_item["revoked_at"] is None
    assert "token" not in listed_item
    assert "token_hash" not in listed_item

    revoke_url = f"{collection}/{body['id']}"
    assert test_client.delete(revoke_url, headers=headers).status_code == 204
    assert test_client.delete(revoke_url, headers=headers).status_code == 204

    with Session(engine) as db:
        assert authenticate_agent_credential(db, token) is None
        credential = db.get(InfrastructureAgentCredential, UUID(body["id"]))
        assert credential is not None
        assert credential.revoked_at is not None
        events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == UUID(organization_id))
                .where(
                    AuditEvent.event_type.in_(
                        [
                            "infrastructure.agent.credential.created",
                            "infrastructure.agent.credential.revoked",
                        ]
                    )
                )
                .order_by(AuditEvent.event_type)
            ).all()
        )
    assert [event.event_type for event in events] == [
        "infrastructure.agent.credential.created",
        "infrastructure.agent.credential.revoked",
    ]
    assert all("token" not in event.details for event in events)
    assert all(token not in str(event.details) for event in events)


def test_viewer_cannot_issue_agent_and_foreign_tenant_is_hidden(client) -> None:
    test_client, engine = client
    organization_a, _, asset_a = _seed_asset(
        engine,
        slug="agent-viewer-a",
        email="agent-owner-a@example.com",
    )
    organization_b, _, asset_b = _seed_asset(
        engine,
        slug="agent-viewer-b",
        email="agent-owner-b@example.com",
    )
    with Session(engine) as db:
        viewer = User(
            email="agent-viewer@example.com",
            display_name="Agent viewer",
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

    csrf_token = _login(test_client, "agent-viewer@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    denied = test_client.post(
        _agent_collection(organization_a, asset_a),
        headers=headers,
        json={"name": "viewer-agent"},
    )
    assert denied.status_code == 403

    foreign = test_client.post(
        _agent_collection(organization_b, asset_b),
        headers=headers,
        json={"name": "foreign-agent"},
    )
    assert foreign.status_code == 404


def test_agent_token_stops_working_when_enrolling_user_is_deactivated(client) -> None:
    test_client, engine = client
    organization_id, user_id, asset_id = _seed_asset(
        engine,
        slug="agent-inactive-owner",
        email="agent-inactive-owner@example.com",
    )
    csrf_token = _login(test_client, "agent-inactive-owner@example.com")
    created = test_client.post(
        _agent_collection(organization_id, asset_id),
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={"name": "delegated-agent"},
    )
    assert created.status_code == 201
    token = created.json()["token"]

    with Session(engine) as db:
        user = db.get(User, UUID(user_id))
        assert user is not None
        user.is_active = False
        db.commit()

    with Session(engine) as db:
        assert authenticate_agent_credential(db, token) is None


def test_expired_agent_token_is_rejected(client) -> None:
    _test_client, engine = client
    organization_id, user_id, asset_id = _seed_asset(
        engine,
        slug="agent-expiry",
        email="agent-expiry@example.com",
    )
    now = datetime(2026, 11, 28, 9, 0, tzinfo=timezone.utc)
    with Session(engine) as db:
        created = create_agent_credential(
            db,
            organization_id=UUID(organization_id),
            asset_id=UUID(asset_id),
            created_by_user_id=UUID(user_id),
            name="short-lived-agent",
            ttl=timedelta(days=1),
            now=now,
        )
        db.commit()
        assert (
            authenticate_agent_credential(
                db,
                created.token,
                now=now + timedelta(days=2),
            )
            is None
        )
