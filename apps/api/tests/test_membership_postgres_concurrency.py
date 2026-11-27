"""PostgreSQL integration coverage for concurrent owner membership mutations."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.main import app
import app.routers.auth as auth_router
import app.routers.organizations as organizations_router
from app.models.audit import AuditEvent
from app.models.identity import Membership, Organization, User
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
