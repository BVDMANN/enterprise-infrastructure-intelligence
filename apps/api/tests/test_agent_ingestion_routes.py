"""Bearer-authenticated agent heartbeat and metric ingestion API tests."""

from __future__ import annotations

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
from app.models.audit import AuditEvent
from app.models.identity import Membership, Organization, User
from app.models.infrastructure import InfrastructureAsset
from app.models.infrastructure_metrics import InfrastructureMetric
from app.services.agents import create_agent_credential
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


def _seed_asset(engine, *, slug: str, email: str) -> tuple[str, str, str]:
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


def _issue_credential(
    client: TestClient,
    organization_id: str,
    asset_id: str,
    email: str,
) -> tuple[str, str, dict[str, str]]:
    csrf_token = _login(client, email)
    collection = (
        f"/api/v1/organizations/{organization_id}/infrastructure/assets/"
        f"{asset_id}/agents"
    )
    response = client.post(
        collection,
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
        json={"name": "linux-proxmox-agent", "expires_in_days": 30},
    )
    assert response.status_code == 201
    body = response.json()
    return body["token"], body["id"], {
        "Origin": ORIGIN,
        "X-CSRF-Token": csrf_token,
    }


def test_agent_can_heartbeat_and_ingest_a_bounded_metric_batch(client) -> None:
    user_client, engine = client
    organization_id, user_id, asset_id = _seed_asset(
        engine,
        slug="agent-ingestion",
        email="agent-ingestion@example.com",
    )
    token, credential_id, _ = _issue_credential(
        user_client,
        organization_id,
        asset_id,
        "agent-ingestion@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    # A separate client proves that agent requests need no browser session cookie.
    with TestClient(app) as agent_client:
        heartbeat = agent_client.post("/api/v1/agent/heartbeat", headers=headers)
        assert heartbeat.status_code == 200
        assert heartbeat.headers["cache-control"] == "no-store"
        assert heartbeat.json()["asset_id"] == asset_id

        ingested = agent_client.post(
            "/api/v1/agent/metrics",
            headers=headers,
            json={
                "samples": [
                    {
                        "metric_name": "CPU.Utilization",
                        "metric_value": "12.5",
                        "unit": "%",
                    },
                    {
                        "metric_name": "memory.used_bytes",
                        "metric_value": "1024",
                        "unit": "bytes",
                    },
                ]
            },
        )

    assert ingested.status_code == 201
    assert ingested.headers["cache-control"] == "no-store"
    assert ingested.json()["asset_id"] == asset_id
    assert ingested.json()["accepted"] == 2

    with Session(engine) as db:
        metrics = list(
            db.scalars(
                select(InfrastructureMetric)
                .where(InfrastructureMetric.organization_id == UUID(organization_id))
                .order_by(InfrastructureMetric.metric_name)
            ).all()
        )
        asset = db.get(InfrastructureAsset, UUID(asset_id))
        audit_events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == UUID(organization_id))
                .where(
                    AuditEvent.event_type == "infrastructure.agent.metrics.ingested"
                )
            ).all()
        )

    assert len(metrics) == 2
    assert {item.ingestion_source for item in metrics} == {"agent_api"}
    assert {item.metric_name for item in metrics} == {
        "cpu.utilization",
        "memory.used_bytes",
    }
    assert all(item.received_at is not None for item in metrics)
    assert asset is not None and asset.last_seen_at is not None
    assert len(audit_events) == 1
    event = audit_events[0]
    assert event.actor_user_id == UUID(user_id)
    assert event.target_id == asset_id
    assert event.details == {
        "actor_type": "infrastructure_agent",
        "agent_credential_id": credential_id,
        "sample_count": 2,
        "ingestion_source": "agent_api",
    }
    assert "metric_value" not in event.details
    assert token not in str(event.details)


def test_missing_invalid_and_revoked_agent_credentials_are_rejected(client) -> None:
    user_client, _engine = client
    organization_id, _user_id, asset_id = _seed_asset(
        _engine,
        slug="agent-auth-rejections",
        email="agent-auth-rejections@example.com",
    )
    token, credential_id, csrf_headers = _issue_credential(
        user_client,
        organization_id,
        asset_id,
        "agent-auth-rejections@example.com",
    )
    collection = (
        f"/api/v1/organizations/{organization_id}/infrastructure/assets/"
        f"{asset_id}/agents/{credential_id}"
    )
    assert user_client.delete(collection, headers=csrf_headers).status_code == 204

    with TestClient(app) as agent_client:
        missing = agent_client.post("/api/v1/agent/heartbeat")
        invalid = agent_client.post(
            "/api/v1/agent/heartbeat",
            headers={"Authorization": "Bearer eii_agent_invalid"},
        )
        revoked = agent_client.post(
            "/api/v1/agent/heartbeat",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert missing.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"
    assert invalid.status_code == 401
    assert revoked.status_code == 401


def test_expired_agent_credential_is_rejected(client) -> None:
    _user_client, engine = client
    organization_id, user_id, asset_id = _seed_asset(
        engine,
        slug="agent-expired",
        email="agent-expired@example.com",
    )
    expired_at = datetime.now(timezone.utc) - timedelta(days=2)
    with Session(engine) as db:
        created = create_agent_credential(
            db,
            organization_id=UUID(organization_id),
            asset_id=UUID(asset_id),
            created_by_user_id=UUID(user_id),
            name="expired-agent",
            ttl=timedelta(days=1),
            now=expired_at,
        )
        db.commit()
    with TestClient(app) as agent_client:
        response = agent_client.post(
            "/api/v1/agent/heartbeat",
            headers={"Authorization": f"Bearer {created.token}"},
        )
    assert response.status_code == 401


def test_invalid_or_unscoped_batches_are_rejected_without_partial_writes(client) -> None:
    user_client, engine = client
    organization_id, _user_id, asset_id = _seed_asset(
        engine,
        slug="agent-invalid-batch",
        email="agent-invalid-batch@example.com",
    )
    token, _credential_id, _csrf_headers = _issue_credential(
        user_client,
        organization_id,
        asset_id,
        "agent-invalid-batch@example.com",
    )
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as agent_client:
        empty = agent_client.post(
            "/api/v1/agent/metrics",
            headers=headers,
            json={"samples": []},
        )
        invalid_metric = agent_client.post(
            "/api/v1/agent/metrics",
            headers=headers,
            json={
                "samples": [
                    {"metric_name": "CPU %", "metric_value": "10", "unit": "%"}
                ]
            },
        )
        unscoped = agent_client.post(
            "/api/v1/agent/metrics",
            headers=headers,
            json={
                "organization_id": "00000000-0000-4000-8000-000000000000",
                "samples": [
                    {"metric_name": "cpu.utilization", "metric_value": "10"}
                ],
            },
        )

    assert empty.status_code == 422
    assert invalid_metric.status_code == 422
    assert unscoped.status_code == 422
    with Session(engine) as db:
        assert db.scalar(select(InfrastructureMetric.id)) is None
        assert (
            db.scalar(
                select(AuditEvent.id).where(
                    AuditEvent.event_type == "infrastructure.agent.metrics.ingested"
                )
            )
            is None
        )
