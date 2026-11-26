"""HTTP organization and RBAC integration tests (P1-A3.1)."""

from __future__ import annotations

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
    def _enable_foreign_keys(
        dbapi_connection, _connection_record
    ):  # noqa: ANN001, ANN202
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


def test_organization_api_requires_a_live_session(client) -> None:
    test_client, _engine = client
    assert test_client.get("/api/v1/organizations").status_code == 401


def test_owner_can_read_only_its_tenant_and_role_catalog(client) -> None:
    test_client, engine = client
    organization_a, _ = _seed_membership(
        engine,
        slug="org-a",
        email="owner-a@example.com",
        role_name="owner",
    )
    organization_b, _ = _seed_membership(
        engine,
        slug="org-b",
        email="owner-b@example.com",
        role_name="owner",
    )
    with Session(engine) as db:
        organization = db.get(Organization, UUID(organization_a))
        viewer = (
            db.query(Role)
            .filter_by(organization_id=organization.id, name="viewer")
            .one()
        )
        inactive = User(
            email="inactive-a@example.com",
            display_name="Inactive member",
            is_active=False,
        )
        db.add(inactive)
        db.flush()
        db.add(
            Membership(
                organization_id=organization.id,
                user_id=inactive.id,
                role_id=viewer.id,
            )
        )
        db.commit()

    _login(test_client, "owner-a@example.com")

    listed = test_client.get("/api/v1/organizations")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [organization_a]

    detail = test_client.get(f"/api/v1/organizations/{organization_a}")
    assert detail.status_code == 200
    assert detail.json()["slug"] == "org-a"

    members = test_client.get(f"/api/v1/organizations/{organization_a}/members")
    assert members.status_code == 200
    assert [item["email"] for item in members.json()] == ["owner-a@example.com"]

    roles = test_client.get(f"/api/v1/organizations/{organization_a}/roles")
    assert roles.status_code == 200
    owner = next(item for item in roles.json() if item["name"] == "owner")
    assert len(owner["permissions"]) == 9
    assert "roles.read" in owner["permissions"]

    cross_tenant = test_client.get(f"/api/v1/organizations/{organization_b}")
    assert cross_tenant.status_code == 404
    assert (
        test_client.get(f"/api/v1/organizations/{organization_b}/members").status_code
        == 404
    )


def test_viewer_can_read_organization_but_not_members_or_roles(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine,
        slug="viewer-org",
        email="viewer@example.com",
        role_name="viewer",
    )
    _login(test_client, "viewer@example.com")

    assert (
        test_client.get(f"/api/v1/organizations/{organization_id}").status_code
        == 200
    )
    assert (
        test_client.get(f"/api/v1/organizations/{organization_id}/members").status_code
        == 403
    )
    assert (
        test_client.get(f"/api/v1/organizations/{organization_id}/roles").status_code
        == 403
    )


def test_membership_without_organization_read_is_not_listed(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine,
        slug="restricted-org",
        email="restricted@example.com",
        role_name="restricted",
    )
    _login(test_client, "restricted@example.com")

    assert test_client.get("/api/v1/organizations").json() == []
    assert (
        test_client.get(f"/api/v1/organizations/{organization_id}").status_code == 403
    )


def test_logout_revokes_session_for_organization_api(client) -> None:
    test_client, engine = client
    _seed_membership(
        engine,
        slug="logout-org",
        email="logout@example.com",
        role_name="owner",
    )
    csrf_token = _login(test_client, "logout@example.com")
    assert test_client.get("/api/v1/organizations").status_code == 200

    logout = test_client.post(
        "/api/v1/auth/logout",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
    )
    assert logout.status_code == 204
    assert "path=/api/v1" in logout.headers["set-cookie"].lower()
    assert test_client.get("/api/v1/organizations").status_code == 401
