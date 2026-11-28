"""Tenant-scoped infrastructure metric API tests (P1-A6.3)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
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


def _sample_payload(
    metric_name: str,
    metric_value: str,
    recorded_at: str,
) -> dict[str, str]:
    return {
        "metric_name": metric_name,
        "metric_value": metric_value,
        "unit": "%",
        "recorded_at": recorded_at,
    }


def test_owner_can_record_and_filter_metric_samples(client) -> None:
    test_client, engine = client
    organization_id, user_id, asset_id = _seed_asset(
        engine,
        slug="metrics-lifecycle",
        email="metrics-owner@example.com",
    )
    csrf_token = _login(test_client, "metrics-owner@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    collection = (
        f"/api/v1/organizations/{organization_id}/infrastructure/assets/"
        f"{asset_id}/metrics"
    )

    older = test_client.post(
        collection,
        headers=headers,
        json=_sample_payload(
            "CPU.Utilization",
            "42.125",
            "2026-11-28T04:00:00+00:00",
        ),
    )
    newer = test_client.post(
        collection,
        headers=headers,
        json=_sample_payload(
            "cpu.utilization",
            "73.5",
            "2026-11-28T05:00:00+00:00",
        ),
    )

    assert older.status_code == 201
    assert newer.status_code == 201
    assert older.json()["metric_name"] == "cpu.utilization"
    assert Decimal(newer.json()["metric_value"]) == Decimal("73.5")
    assert newer.json()["unit"] == "%"

    listed = test_client.get(collection)
    assert listed.status_code == 200
    assert [item["metric_value"] for item in listed.json()] == [
        "73.500000",
        "42.125000",
    ]

    filtered = test_client.get(f"{collection}?metric_name=cpu.utilization&limit=1")
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["id"] == newer.json()["id"]

    bounded = test_client.get(
        f"{collection}?since=2026-11-28T04:30:00%2B00:00"
        "&until=2026-11-28T05:30:00%2B00:00"
    )
    assert bounded.status_code == 200
    assert [item["id"] for item in bounded.json()] == [newer.json()["id"]]

    with Session(engine) as db:
        rows = list(
            db.scalars(
                select(InfrastructureMetric).where(
                    InfrastructureMetric.organization_id == UUID(organization_id)
                )
            ).all()
        )
    assert len(rows) == 2
    assert all(row.received_at is not None for row in rows)

    with Session(engine) as db:
        audit_events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == UUID(organization_id))
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            ).all()
        )
    assert len(audit_events) == 2
    assert {item.event_type for item in audit_events} == {
        "infrastructure.metric.recorded"
    }
    assert all(item.actor_user_id == UUID(user_id) for item in audit_events)
    assert all(item.target_type == "infrastructure_asset" for item in audit_events)
    assert all(item.target_id == asset_id for item in audit_events)
    assert {item.details["metric_name"] for item in audit_events} == {"cpu.utilization"}
    assert all(
        item.details["ingestion_source"] == "operator_api" for item in audit_events
    )
    assert all("metric_value" not in item.details for item in audit_events)


def test_viewer_can_read_but_cannot_record_metric_samples(client) -> None:
    test_client, engine = client
    organization_id, _, asset_id = _seed_asset(
        engine,
        slug="metrics-viewer",
        email="metrics-viewer-owner@example.com",
    )
    with Session(engine) as db:
        viewer = User(
            email="metrics-viewer@example.com",
            display_name="Metrics viewer",
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
        db.add(
            InfrastructureMetric(
                organization_id=UUID(organization_id),
                asset_id=UUID(asset_id),
                metric_name="cpu.utilization",
                metric_value=Decimal("25"),
                unit="%",
                recorded_at=datetime(2026, 11, 28, 4, tzinfo=timezone.utc),
            )
        )
        db.commit()

    csrf_token = _login(test_client, "metrics-viewer@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    collection = (
        f"/api/v1/organizations/{organization_id}/infrastructure/assets/"
        f"{asset_id}/metrics"
    )
    listed = test_client.get(collection)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    denied = test_client.post(
        collection,
        headers=headers,
        json=_sample_payload(
            "cpu.utilization",
            "90",
            "2026-11-28T05:00:00+00:00",
        ),
    )
    assert denied.status_code == 403

    with Session(engine) as db:
        metric_events = list(
            db.scalars(
                select(AuditEvent).where(
                    AuditEvent.event_type == "infrastructure.metric.recorded"
                )
            ).all()
        )
    assert metric_events == []


def test_metrics_are_hidden_across_tenants(client) -> None:
    test_client, engine = client
    organization_a, _, asset_a = _seed_asset(
        engine,
        slug="metrics-tenant-a",
        email="metrics-owner-a@example.com",
    )
    organization_b, _, asset_b = _seed_asset(
        engine,
        slug="metrics-tenant-b",
        email="metrics-owner-b@example.com",
    )
    csrf_token = _login(test_client, "metrics-owner-a@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    foreign_collection = (
        f"/api/v1/organizations/{organization_b}/infrastructure/assets/"
        f"{asset_b}/metrics"
    )
    assert test_client.get(foreign_collection).status_code == 404

    denied = test_client.post(
        foreign_collection,
        headers=headers,
        json=_sample_payload(
            "cpu.utilization",
            "90",
            "2026-11-28T05:00:00+00:00",
        ),
    )
    assert denied.status_code == 404
    own_collection = (
        f"/api/v1/organizations/{organization_a}/infrastructure/assets/"
        f"{asset_a}/metrics"
    )
    assert test_client.get(own_collection).status_code == 200

    with Session(engine) as db:
        foreign_events = list(
            db.scalars(
                select(AuditEvent)
                .where(AuditEvent.organization_id == UUID(organization_b))
                .where(AuditEvent.event_type == "infrastructure.metric.recorded")
            ).all()
        )
    assert foreign_events == []


def test_metric_payload_rejects_invalid_names_nonfinite_values_and_future_time(
    client,
) -> None:
    test_client, _engine = client
    organization_id, _, asset_id = _seed_asset(
        _engine,
        slug="metrics-validation",
        email="metrics-validation@example.com",
    )
    csrf_token = _login(test_client, "metrics-validation@example.com")
    headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf_token}
    collection = (
        f"/api/v1/organizations/{organization_id}/infrastructure/assets/"
        f"{asset_id}/metrics"
    )

    invalid_name = test_client.post(
        collection,
        headers=headers,
        json=_sample_payload(
            "CPU utilization",
            "12",
            "2026-11-28T05:00:00+00:00",
        ),
    )
    assert invalid_name.status_code == 422

    nonfinite = test_client.post(
        collection,
        headers=headers,
        json=_sample_payload(
            "cpu.utilization",
            "NaN",
            "2026-11-28T05:00:00+00:00",
        ),
    )
    assert nonfinite.status_code == 422

    future = test_client.post(
        collection,
        headers=headers,
        json=_sample_payload(
            "cpu.utilization",
            "12",
            "2099-01-01T00:00:00+00:00",
        ),
    )
    assert future.status_code == 422
