"""HTTP organization creation, rename and soft-delete tests (P1-A1 completion)."""

from __future__ import annotations

from uuid import UUID, uuid4

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
PASSWORD = "correct-horse-battery-staple"


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


def _seed_user(engine, *, email: str) -> str:
    with Session(engine) as db:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.commit()
        return str(user.id)


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
        role = next((item for item in roles if item.name == role_name), None)
        if role is None:
            role = Role(
                organization_id=organization.id,
                name=role_name,
                description="Test-only restricted role",
                is_system=False,
            )
            db.add(role)
            db.flush()

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
    assert "path=/api/v1" in response.headers["set-cookie"].lower()
    return response.json()["csrf_token"]


def _headers(csrf: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf}


def test_create_organization_requires_a_live_session(client) -> None:
    test_client, _engine = client
    response = test_client.post(
        "/api/v1/organizations",
        headers={"Origin": ORIGIN},
        json={"name": "Acme", "slug": "acme"},
    )
    assert response.status_code == 401


def test_create_organization_requires_csrf(client) -> None:
    test_client, engine = client
    _seed_user(engine, email="creator@example.com")
    _login(test_client, "creator@example.com")
    response = test_client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme"},
    )
    assert response.status_code == 403


def test_creator_becomes_owner_and_creation_is_audited(client) -> None:
    test_client, engine = client
    _seed_user(engine, email="creator@example.com")
    csrf = _login(test_client, "creator@example.com")

    response = test_client.post(
        "/api/v1/organizations",
        headers=_headers(csrf),
        json={"name": "Acme Corp", "slug": "acme"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Corp"
    assert body["slug"] == "acme"
    organization_id = body["id"]

    listed = test_client.get("/api/v1/organizations")
    assert listed.status_code == 200
    assert [item["slug"] for item in listed.json()] == ["acme"]

    members = test_client.get(f"/api/v1/organizations/{organization_id}/members")
    assert members.status_code == 200
    assert len(members.json()) == 1
    assert members.json()[0]["email"] == "creator@example.com"
    assert members.json()[0]["role"] == "owner"

    roles = test_client.get(f"/api/v1/organizations/{organization_id}/roles")
    assert roles.status_code == 200
    assert {item["name"] for item in roles.json()} == {
        "owner",
        "admin",
        "member",
        "viewer",
    }

    with Session(engine) as db:
        event = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.organization_id == UUID(organization_id))
            .where(AuditEvent.event_type == "organization.created")
        )
        assert event is not None
        assert event.details["slug"] == "acme"


def test_create_organization_rejects_duplicate_slug(client) -> None:
    test_client, engine = client
    _seed_user(engine, email="creator@example.com")
    csrf = _login(test_client, "creator@example.com")

    payload = {"name": "Acme", "slug": "acme"}
    assert (
        test_client.post(
            "/api/v1/organizations", headers=_headers(csrf), json=payload
        ).status_code
        == 201
    )
    response = test_client.post(
        "/api/v1/organizations",
        headers=_headers(csrf),
        json={"name": "Acme Again", "slug": "acme"},
    )
    assert response.status_code == 409


def test_create_organization_rejects_invalid_slug(client) -> None:
    test_client, engine = client
    _seed_user(engine, email="creator@example.com")
    csrf = _login(test_client, "creator@example.com")

    response = test_client.post(
        "/api/v1/organizations",
        headers=_headers(csrf),
        json={"name": "Bad", "slug": "Bad Slug!"},
    )
    assert response.status_code == 422


def test_create_organization_normalizes_slug(client) -> None:
    test_client, engine = client
    _seed_user(engine, email="creator@example.com")
    csrf = _login(test_client, "creator@example.com")

    response = test_client.post(
        "/api/v1/organizations",
        headers=_headers(csrf),
        json={"name": "Acme", "slug": "  Acme-Corp "},
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "acme-corp"


def test_owner_renames_organization_and_rename_is_audited(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    response = test_client.patch(
        f"/api/v1/organizations/{organization_id}",
        headers=_headers(csrf),
        json={"name": "Renamed Org"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Org"
    assert response.json()["slug"] == "org-a"

    with Session(engine) as db:
        event = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.organization_id == UUID(organization_id))
            .where(AuditEvent.event_type == "organization.updated")
        )
        assert event is not None
        assert event.details["previous_name"] == "Org-A"
        assert event.details["name"] == "Renamed Org"


def test_rename_requires_organization_manage(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    with Session(engine) as db:
        member = User(
            email="member@example.com",
            display_name="member",
            password_hash=hash_password(PASSWORD),
        )
        db.add(member)
        db.flush()
        role = db.scalar(
            select(Role).where(
                Role.organization_id == UUID(organization_id),
                Role.name == "member",
            )
        )
        db.add(
            Membership(
                organization_id=UUID(organization_id),
                user_id=member.id,
                role_id=role.id,
            )
        )
        db.commit()
    csrf = _login(test_client, "member@example.com")

    response = test_client.patch(
        f"/api/v1/organizations/{organization_id}",
        headers=_headers(csrf),
        json={"name": "Renamed Org"},
    )
    assert response.status_code == 403


def test_owner_soft_deletes_organization(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    response = test_client.delete(
        f"/api/v1/organizations/{organization_id}", headers=_headers(csrf)
    )
    assert response.status_code == 204

    assert (
        test_client.get(f"/api/v1/organizations/{organization_id}").status_code == 404
    )
    listed = test_client.get("/api/v1/organizations")
    assert listed.status_code == 200
    assert listed.json() == []

    with Session(engine) as db:
        event = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.organization_id == UUID(organization_id))
            .where(AuditEvent.event_type == "organization.deleted")
        )
        assert event is not None
        assert event.details["slug"] == "org-a"
        organization = db.get(Organization, UUID(organization_id))
        assert organization is not None
        assert organization.deleted_at is not None


def test_delete_requires_organization_manage(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    with Session(engine) as db:
        admin = User(
            email="admin@example.com",
            display_name="admin",
            password_hash=hash_password(PASSWORD),
        )
        db.add(admin)
        db.flush()
        role = db.scalar(
            select(Role).where(
                Role.organization_id == UUID(organization_id),
                Role.name == "admin",
            )
        )
        db.add(
            Membership(
                organization_id=UUID(organization_id),
                user_id=admin.id,
                role_id=role.id,
            )
        )
        db.commit()
    csrf = _login(test_client, "admin@example.com")

    response = test_client.delete(
        f"/api/v1/organizations/{organization_id}", headers=_headers(csrf)
    )
    assert response.status_code == 403
    assert (
        test_client.get(f"/api/v1/organizations/{organization_id}").status_code == 200
    )


def test_delete_unknown_organization_is_404(client) -> None:
    test_client, engine = client
    _seed_membership(engine, slug="org-a", email="owner@example.com", role_name="owner")
    csrf = _login(test_client, "owner@example.com")

    response = test_client.delete(
        f"/api/v1/organizations/{uuid4()}", headers=_headers(csrf)
    )
    assert response.status_code == 404
