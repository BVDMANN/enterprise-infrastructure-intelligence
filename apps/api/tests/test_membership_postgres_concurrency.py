"""PostgreSQL integration coverage for concurrent owner membership mutations."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.main import app
import app.routers.auth as auth_router
import app.routers.organizations as organizations_router
import app.services.invitations as invitations_service
from app.models.audit import AuditEvent
from app.models.identity import Invitation, Membership, Organization, User
from app.models.rbac import Role
from app.services.passwords import hash_password
from app.services.rbac import create_default_roles_for_organization

pytestmark = pytest.mark.skipif(
    os.getenv("EII_POSTGRES_INTEGRATION") != "1",
    reason="Requires the dedicated PostgreSQL integration job",
)

ORIGIN = "http://localhost:3000"
PASSWORD = "eii-postgres-integration-password"


def _login(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": ORIGIN},
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    return response.json()["csrf_token"]


def test_concurrent_owner_demotions_preserve_one_active_owner(monkeypatch) -> None:
    """Two authorized owners cannot demote each other concurrently."""
    assert engine.dialect.name == "postgresql"

    suffix = uuid4().hex
    organization_slug = f"membership-concurrency-{suffix}"
    owner_a_email = f"owner-a-{suffix}@example.test"
    owner_b_email = f"owner-b-{suffix}@example.test"

    with SessionLocal() as db:
        organization = Organization(
            name="Membership concurrency integration",
            slug=organization_slug,
        )
        owner_a = User(
            email=owner_a_email,
            display_name="Concurrent owner A",
            password_hash=hash_password(PASSWORD),
        )
        owner_b = User(
            email=owner_b_email,
            display_name="Concurrent owner B",
            password_hash=hash_password(PASSWORD),
        )
        db.add_all([organization, owner_a, owner_b])
        db.flush()

        roles = {
            role.name: role
            for role in create_default_roles_for_organization(db, organization.id)
        }
        owner_role = roles["owner"]
        member_role_id = roles["member"].id
        membership_a = Membership(
            organization_id=organization.id,
            user_id=owner_a.id,
            role_id=owner_role.id,
        )
        membership_b = Membership(
            organization_id=organization.id,
            user_id=owner_b.id,
            role_id=owner_role.id,
        )
        db.add_all([membership_a, membership_b])
        db.commit()

        organization_id = organization.id
        membership_a_id = membership_a.id
        membership_b_id = membership_b.id

    monkeypatch.setattr(
        auth_router,
        "_enforce_login_rate_limit",
        lambda _request, _email: None,
    )

    original_lock = organizations_router._lock_organization_for_membership_mutation
    rendezvous = Barrier(2)
    counter_lock = Lock()
    lock_calls = 0

    def synchronize_before_tenant_lock(db: Session, tenant_id) -> None:
        nonlocal lock_calls
        with counter_lock:
            lock_calls += 1
        # Both requests must pass session/permission dependencies before either
        # can acquire the tenant lock or change an owner membership.
        rendezvous.wait(timeout=20)
        original_lock(db, tenant_id)

    monkeypatch.setattr(
        organizations_router,
        "_lock_organization_for_membership_mutation",
        synchronize_before_tenant_lock,
    )

    with TestClient(app) as client_a, TestClient(app) as client_b:
        csrf_a = _login(client_a, owner_a_email)
        csrf_b = _login(client_b, owner_b_email)

        def demote(client: TestClient, membership_id, csrf_token: str):
            return client.patch(
                f"/api/v1/organizations/{organization_id}/memberships/{membership_id}",
                headers={"Origin": ORIGIN, "X-CSRF-Token": csrf_token},
                json={"role_id": str(member_role_id)},
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(demote, client_a, membership_b_id, csrf_a)
            future_b = executor.submit(demote, client_b, membership_a_id, csrf_b)
            response_a = future_a.result(timeout=40)
            response_b = future_b.result(timeout=40)

    assert lock_calls == 2
    assert sorted([response_a.status_code, response_b.status_code]) == [200, 409]

    with SessionLocal() as db:
        owner_memberships = db.execute(
            select(Membership.id)
            .join(
                Role,
                and_(
                    Role.id == Membership.role_id,
                    Role.organization_id == Membership.organization_id,
                ),
            )
            .where(Membership.organization_id == organization_id)
            .where(Role.name == "owner")
        ).all()
        assert len(owner_memberships) == 1

        role_changes = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.organization_id == organization_id)
            .where(AuditEvent.event_type == "membership.role_changed")
        ).all()
        assert len(role_changes) == 1


def _seed_invitation_organization() -> tuple[str, str, str]:
    """Create a unique tenant with an owner and return its member role."""
    suffix = uuid4().hex
    owner_email = f"invitation-owner-{suffix}@example.test"
    with SessionLocal() as db:
        organization = Organization(
            name="Invitation concurrency integration",
            slug=f"invitation-concurrency-{suffix}",
        )
        owner = User(
            email=owner_email,
            display_name="Invitation owner",
            password_hash=hash_password(PASSWORD),
        )
        db.add_all([organization, owner])
        db.flush()
        roles = {
            role.name: role
            for role in create_default_roles_for_organization(db, organization.id)
        }
        db.add(
            Membership(
                organization_id=organization.id,
                user_id=owner.id,
                role_id=roles["owner"].id,
            )
        )
        db.commit()
        return str(organization.id), owner_email, str(roles["member"].id)


def _create_invitation(
    client: TestClient,
    csrf: str,
    organization_id: str,
    role_id: str,
    email: str,
) -> dict:
    response = client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
        json={"email": email, "role_id": role_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _pause_first_invitation_acceptance(monkeypatch):
    """Pause the first accept after it has acquired the invitation row lock."""
    loaded = Event()
    release = Event()
    guard = Lock()
    first_call = False
    original = invitations_service._find_pending_invitation

    def pause_after_lock(db: Session, *, token_hash: str):
        nonlocal first_call
        invitation = original(db, token_hash=token_hash)
        if invitation is not None:
            with guard:
                should_pause = not first_call
                if should_pause:
                    first_call = True
            if should_pause:
                loaded.set()
                if not release.wait(timeout=20):
                    raise TimeoutError("Timed out waiting to release invitation lock")
        return invitation

    monkeypatch.setattr(
        invitations_service, "_find_pending_invitation", pause_after_lock
    )
    return loaded, release


def test_concurrent_invitation_accept_and_revoke_are_serialized(monkeypatch) -> None:
    """A revocation cannot pass an acceptance holding the invitation row lock."""
    assert engine.dialect.name == "postgresql"
    organization_id, owner_email, member_role_id = _seed_invitation_organization()
    invitee_email = f"invitee-{uuid4().hex}@example.test"

    monkeypatch.setattr(
        auth_router,
        "_enforce_login_rate_limit",
        lambda _request, _email: None,
    )

    with TestClient(app) as owner_client, TestClient(app) as accept_client:
        csrf = _login(owner_client, owner_email)
        invitation = _create_invitation(
            owner_client,
            csrf,
            organization_id,
            member_role_id,
            invitee_email,
        )
        loaded, release = _pause_first_invitation_acceptance(monkeypatch)
        revocation_finished = Event()

        def accept():
            return accept_client.post(
                f"/api/v1/invitations/{invitation['token']}/accept",
                json={"display_name": "Concurrent invitee", "password": PASSWORD},
            )

        def revoke():
            try:
                return owner_client.delete(
                    f"/api/v1/organizations/{organization_id}/invitations/"
                    f"{invitation['id']}",
                    headers={"Origin": ORIGIN, "X-CSRF-Token": csrf},
                )
            finally:
                revocation_finished.set()

        with ThreadPoolExecutor(max_workers=2) as executor:
            accept_future = executor.submit(accept)
            assert loaded.wait(timeout=10), "Acceptance did not acquire its row lock"
            revoke_future = executor.submit(revoke)
            try:
                revoke_blocked = not revocation_finished.wait(timeout=1)
            finally:
                release.set()
            accept_response = accept_future.result(timeout=30)
            revoke_response = revoke_future.result(timeout=30)

    assert revoke_blocked, "Revocation completed while acceptance held the row lock"
    assert accept_response.status_code == 200, accept_response.text
    assert revoke_response.status_code == 409, revoke_response.text

    with SessionLocal() as db:
        stored = db.get(Invitation, UUID(invitation["id"]))
        assert stored is not None
        assert stored.accepted_at is not None
        assert stored.revoked_at is None
        membership_count = db.scalar(
            select(func.count(Membership.id)).where(
                Membership.organization_id == UUID(organization_id),
                Membership.user_id == UUID(accept_response.json()["user_id"]),
            )
        )
        assert membership_count == 1


def test_concurrent_invitation_acceptance_is_single_use(monkeypatch) -> None:
    """Two simultaneous acceptors cannot create two memberships from one token."""
    assert engine.dialect.name == "postgresql"
    organization_id, owner_email, member_role_id = _seed_invitation_organization()
    invitee_email = f"double-accept-{uuid4().hex}@example.test"

    monkeypatch.setattr(
        auth_router,
        "_enforce_login_rate_limit",
        lambda _request, _email: None,
    )

    with (
        TestClient(app) as owner_client,
        TestClient(app) as first_client,
        TestClient(app) as second_client,
    ):
        csrf = _login(owner_client, owner_email)
        invitation = _create_invitation(
            owner_client,
            csrf,
            organization_id,
            member_role_id,
            invitee_email,
        )
        loaded, release = _pause_first_invitation_acceptance(monkeypatch)
        second_finished = Event()

        def accept(client: TestClient):
            return client.post(
                f"/api/v1/invitations/{invitation['token']}/accept",
                json={"display_name": "Concurrent invitee", "password": PASSWORD},
            )

        def accept_second():
            try:
                return accept(second_client)
            finally:
                second_finished.set()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(accept, first_client)
            assert loaded.wait(timeout=10), (
                "First acceptance did not acquire its row lock"
            )
            second_future = executor.submit(accept_second)
            try:
                second_blocked = not second_finished.wait(timeout=1)
            finally:
                release.set()
            first_response = first_future.result(timeout=30)
            second_response = second_future.result(timeout=30)

    assert second_blocked, "Second acceptance did not wait for the invitation row lock"
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 404, second_response.text

    with SessionLocal() as db:
        stored = db.get(Invitation, UUID(invitation["id"]))
        assert stored is not None
        assert stored.accepted_at is not None
        assert stored.revoked_at is None
        membership_count = db.scalar(
            select(func.count(Membership.id)).where(
                Membership.organization_id == UUID(organization_id),
                Membership.user_id == UUID(first_response.json()["user_id"]),
            )
        )
        assert membership_count == 1
