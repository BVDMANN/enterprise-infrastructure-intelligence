"""HTTP member status (deactivate / reactivate) tests (P1-A1 completion)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
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


def _seed_membership(
    engine,
    *,
    slug: str,
    email: str,
    role_name: str,
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
        role = next((item for item in roles if item.name == role_name), None)
        membership = Membership(
            organization_id=organization.id,
            user_id=user.id,
            role_id=role.id,
        )
        db.add(membership)
        db.commit()
        return str(organization.id), str(user.id), str(membership.id)


def _seed_member(engine, *, organization_id: str, email: str, role_name: str) -> str:
    with Session(engine) as db:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password(PASSWORD),
        )
        db.add(user)
        db.flush()
        role = db.scalar(
            select(Role).where(
                Role.organization_id == UUID(organization_id),
                Role.name == role_name,
            )
        )
        membership = Membership(
            organization_id=UUID(organization_id),
            user_id=user.id,
            role_id=role.id,
        )
        db.add(membership)
        db.commit()
        return str(membership.id)


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


def _set_status(
    test_client: TestClient,
    csrf: str,
    organization_id: str,
    membership_id: str,
    *,
    is_active: bool,
):
    return test_client.patch(
        f"/api/v1/organizations/{organization_id}/members/{membership_id}/status",
        headers=_headers(csrf),
        json={"is_active": is_active},
    )


def test_owner_deactivates_member_and_login_fails(client) -> None:
    test_client, engine = client
    organization_id, _, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    membership_id = _seed_member(
        engine,
        organization_id=organization_id,
        email="member@example.com",
        role_name="member",
    )
    csrf = _login(test_client, "owner@example.com")

    response = _set_status(
        test_client, csrf, organization_id, membership_id, is_active=False
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["email"] == "member@example.com"

    # The deactivated member is hidden from the default list and cannot log in.
    members = test_client.get(f"/api/v1/organizations/{organization_id}/members")
    assert members.status_code == 200
    assert [item["email"] for item in members.json()] == ["owner@example.com"]
    login = test_client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "member@example.com", "password": PASSWORD},
    )
    assert login.status_code == 401

    # include_inactive shows the deactivated member with its status.
    all_members = test_client.get(
        f"/api/v1/organizations/{organization_id}/members?include_inactive=true"
    )
    assert all_members.status_code == 200
    deactivated = next(
        item for item in all_members.json() if item["email"] == "member@example.com"
    )
    assert deactivated["is_active"] is False

    with Session(engine) as db:
        event = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.organization_id == UUID(organization_id))
            .where(AuditEvent.event_type == "user.deactivated")
        )
        assert event is not None
        assert event.target_type == "user"


def test_owner_reactivates_member_and_login_works_again(client) -> None:
    test_client, engine = client
    organization_id, _, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    membership_id = _seed_member(
        engine,
        organization_id=organization_id,
        email="member@example.com",
        role_name="member",
    )
    csrf = _login(test_client, "owner@example.com")

    assert (
        _set_status(
            test_client, csrf, organization_id, membership_id, is_active=False
        ).status_code
        == 200
    )
    response = _set_status(
        test_client, csrf, organization_id, membership_id, is_active=True
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is True

    login = test_client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "member@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200

    with Session(engine) as db:
        event = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.organization_id == UUID(organization_id))
            .where(AuditEvent.event_type == "user.reactivated")
        )
        assert event is not None


def test_status_change_requires_members_manage(client) -> None:
    test_client, engine = client
    organization_id, _, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    member_a = _seed_member(
        engine,
        organization_id=organization_id,
        email="member-a@example.com",
        role_name="member",
    )
    _seed_member(
        engine,
        organization_id=organization_id,
        email="member-b@example.com",
        role_name="member",
    )
    csrf = _login(test_client, "member-a@example.com")

    response = _set_status(
        test_client, csrf, organization_id, member_a, is_active=False
    )
    assert response.status_code == 403


def test_member_cannot_change_their_own_status(client) -> None:
    test_client, engine = client
    organization_id, _, membership_id = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    response = _set_status(
        test_client, csrf, organization_id, membership_id, is_active=False
    )
    assert response.status_code == 409


def test_last_active_owner_cannot_be_deactivated(client) -> None:
    test_client, engine = client
    organization_id, _, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    owner_membership = _seed_member(
        engine,
        organization_id=organization_id,
        email="owner2@example.com",
        role_name="owner",
    )
    # The admin (members.manage, not owner) deactivating the
    # sole remaining owner must be refused.
    _seed_member(
        engine,
        organization_id=organization_id,
        email="admin@example.com",
        role_name="admin",
    )
    with Session(engine) as db:
        # Remove the first owner so owner2 is the last active owner.
        first_owner = db.scalar(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(Membership.organization_id == UUID(organization_id))
            .where(User.email == "owner@example.com")
        )
        db.delete(first_owner)
        db.commit()
    csrf = _login(test_client, "admin@example.com")

    response = _set_status(
        test_client, csrf, organization_id, owner_membership, is_active=False
    )
    assert response.status_code == 409

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "owner2@example.com"))
        assert user.is_active is True


def test_status_change_is_idempotent(client) -> None:
    test_client, engine = client
    organization_id, _, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    membership_id = _seed_member(
        engine,
        organization_id=organization_id,
        email="member@example.com",
        role_name="member",
    )
    csrf = _login(test_client, "owner@example.com")

    first = _set_status(
        test_client, csrf, organization_id, membership_id, is_active=False
    )
    assert first.status_code == 200
    second = _set_status(
        test_client, csrf, organization_id, membership_id, is_active=False
    )
    assert second.status_code == 200
    assert second.json()["is_active"] is False

    with Session(engine) as db:
        count = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.organization_id == UUID(organization_id))
            .where(AuditEvent.event_type == "user.deactivated")
        )
        assert count == 1


def test_status_change_unknown_membership_is_404(client) -> None:
    test_client, engine = client
    organization_id, _, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    response = _set_status(
        test_client, csrf, organization_id, str(uuid4()), is_active=False
    )
    assert response.status_code == 404
