"""HTTP member invitation tests: manual link, double-mode accept (P1-A1)."""

from __future__ import annotations

import hashlib
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
from app.models.identity import Invitation, Membership, Organization, User
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
        db.add(
            Membership(
                organization_id=organization.id,
                user_id=user.id,
                role_id=role.id,
            )
        )
        db.commit()
        return str(organization.id), str(user.id)


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


def _role_id(engine, organization_id: str, name: str) -> str:
    with Session(engine) as db:
        role = db.scalar(
            select(Role).where(
                Role.organization_id == UUID(organization_id),
                Role.name == name,
            )
        )
        return str(role.id)


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


def _invite(
    test_client: TestClient,
    csrf: str,
    organization_id: str,
    *,
    email: str,
    role_id: str,
) -> dict:
    response = test_client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=_headers(csrf),
        json={"email": email, "role_id": role_id},
    )
    assert response.status_code == 201
    return response.json()


def test_create_invitation_requires_members_manage(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    member_id = _seed_user(engine, email="member@example.com")
    with Session(engine) as db:
        db.add(
            Membership(
                organization_id=UUID(organization_id),
                user_id=UUID(member_id),
                role_id=UUID(_role_id(engine, organization_id, "member")),
            )
        )
        db.commit()
    csrf = _login(test_client, "member@example.com")

    response = test_client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=_headers(csrf),
        json={
            "email": "new@example.com",
            "role_id": _role_id(engine, organization_id, "member"),
        },
    )
    assert response.status_code == 403


def test_owner_creates_invitation_token_returned_once_and_never_stored(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="new@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )
    assert body["status"] == "pending"
    assert body["email"] == "new@example.com"
    assert body["role_name"] == "member"
    assert body["accept_path"] == f"/invitations/{body['token']}"
    assert len(body["token"]) == 43

    # The token never appears in the list response or in audit details.
    listed = test_client.get(f"/api/v1/organizations/{organization_id}/invitations")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "token" not in listed.json()[0]
    assert listed.json()[0]["status"] == "pending"

    with Session(engine) as db:
        invitation = db.scalar(
            select(Invitation).where(
                Invitation.organization_id == UUID(organization_id)
            )
        )
        assert invitation is not None
        assert invitation.token_hash != body["token"]
        assert (
            invitation.token_hash
            == hashlib.sha256(body["token"].encode("ascii")).hexdigest()
        )
        event = db.scalar(
            select(AuditEvent)
            .where(AuditEvent.organization_id == UUID(organization_id))
            .where(AuditEvent.event_type == "invitation.created")
        )
        assert event is not None
        assert body["token"] not in str(event.details)


def test_create_invitation_rejects_duplicate_pending(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")
    role_id = _role_id(engine, organization_id, "member")

    _invite(
        test_client, csrf, organization_id, email="new@example.com", role_id=role_id
    )
    response = test_client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=_headers(csrf),
        json={"email": "new@example.com", "role_id": role_id},
    )
    assert response.status_code == 409


def test_create_invitation_rejects_existing_member(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    response = test_client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=_headers(csrf),
        json={
            "email": "owner@example.com",
            "role_id": _role_id(engine, organization_id, "member"),
        },
    )
    assert response.status_code == 409


def test_create_invitation_rejects_foreign_role(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    organization_b, _ = _seed_membership(
        engine, slug="org-b", email="owner-b@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    response = test_client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers=_headers(csrf),
        json={
            "email": "new@example.com",
            "role_id": _role_id(engine, organization_b, "member"),
        },
    )
    assert response.status_code == 404


def test_invitation_preview_is_public(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="new@example.com",
        role_id=_role_id(engine, organization_id, "viewer"),
    )

    response = test_client.get(f"/api/v1/invitations/{body['token']}")
    assert response.status_code == 200
    preview = response.json()
    assert preview["organization_name"] == "Org-A"
    assert preview["organization_slug"] == "org-a"
    assert preview["role_name"] == "viewer"
    assert preview["email"] == "new@example.com"
    assert "token" not in preview


def test_invitation_preview_rejects_unknown_token(client) -> None:
    test_client, _engine = client
    response = test_client.get("/api/v1/invitations/not-a-real-token")
    assert response.status_code == 404


def test_accept_invitation_creates_account_by_password(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="new@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )

    # Anonymous accept: drop the owner's session cookie first.
    test_client.cookies.clear()
    response = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        json={"display_name": "New Member", "password": PASSWORD},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["organization_id"] == organization_id
    assert result["email"] == "new@example.com"
    assert result["role_name"] == "member"

    # The new account can log in and is listed as a member.
    login = test_client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": "new@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200

    _login(test_client, "owner@example.com")
    members = test_client.get(
        f"/api/v1/organizations/{organization_id}/members",
        headers={"Origin": ORIGIN},
    )
    assert members.status_code == 200
    assert {item["email"] for item in members.json()} == {
        "owner@example.com",
        "new@example.com",
    }
    listed = test_client.get(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers={"Origin": ORIGIN},
    )
    assert listed.json()[0]["status"] == "accepted"


def test_accept_invitation_authenticates_existing_account_by_password(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    existing_id = _seed_user(engine, email="existing@example.com")
    csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="existing@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )

    # Anonymous accept: drop the owner's session cookie first.
    test_client.cookies.clear()
    response = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        json={"password": PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == existing_id


def test_accept_invitation_rejects_wrong_password(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    _seed_user(engine, email="existing@example.com")
    csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="existing@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )

    # Anonymous accept: drop the owner's session cookie first.
    test_client.cookies.clear()
    response = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        json={"password": "wrong-password-123"},
    )
    assert response.status_code == 401


def test_accept_invitation_authenticated_mode(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    _seed_user(engine, email="invitee@example.com")
    owner_csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        owner_csrf,
        organization_id,
        email="invitee@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )

    invitee_csrf = _login(test_client, "invitee@example.com")
    response = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        headers=_headers(invitee_csrf),
        json={},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "invitee@example.com"


def test_accept_invitation_authenticated_mode_rejects_other_user(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    _seed_user(engine, email="invitee@example.com")
    _seed_user(engine, email="other@example.com")
    owner_csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        owner_csrf,
        organization_id,
        email="invitee@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )

    other_csrf = _login(test_client, "other@example.com")
    response = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        headers=_headers(other_csrf),
        json={},
    )
    assert response.status_code == 403


def test_accept_invitation_is_single_use(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="new@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )

    # Anonymous accept: drop the owner's session cookie first.
    test_client.cookies.clear()
    first = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        json={"display_name": "New Member", "password": PASSWORD},
    )
    assert first.status_code == 200
    # Anonymous accept: drop the owner's session cookie first.
    test_client.cookies.clear()
    second = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        json={"display_name": "New Member", "password": PASSWORD},
    )
    assert second.status_code == 404


def test_revoke_invitation_is_idempotent(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="new@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )

    response = test_client.delete(
        f"/api/v1/organizations/{organization_id}/invitations/{body['id']}",
        headers=_headers(csrf),
    )
    assert response.status_code == 204
    again = test_client.delete(
        f"/api/v1/organizations/{organization_id}/invitations/{body['id']}",
        headers=_headers(csrf),
    )
    assert again.status_code == 204

    preview = test_client.get(f"/api/v1/invitations/{body['token']}")
    assert preview.status_code == 404
    listed = test_client.get(f"/api/v1/organizations/{organization_id}/invitations")
    assert listed.json()[0]["status"] == "revoked"


def test_revoke_accepted_invitation_is_rejected(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")
    body = _invite(
        test_client,
        csrf,
        organization_id,
        email="new@example.com",
        role_id=_role_id(engine, organization_id, "member"),
    )
    # Anonymous accept: drop the owner's session cookie first.
    test_client.cookies.clear()
    accepted = test_client.post(
        f"/api/v1/invitations/{body['token']}/accept",
        json={"display_name": "New Member", "password": PASSWORD},
    )
    assert accepted.status_code == 200

    csrf = _login(test_client, "owner@example.com")
    response = test_client.delete(
        f"/api/v1/organizations/{organization_id}/invitations/{body['id']}",
        headers=_headers(csrf),
    )
    assert response.status_code == 409


def test_revoke_unknown_invitation_is_404(client) -> None:
    test_client, engine = client
    organization_id, _ = _seed_membership(
        engine, slug="org-a", email="owner@example.com", role_name="owner"
    )
    csrf = _login(test_client, "owner@example.com")

    response = test_client.delete(
        f"/api/v1/organizations/{organization_id}/invitations/{uuid4()}",
        headers=_headers(csrf),
    )
    assert response.status_code == 404
