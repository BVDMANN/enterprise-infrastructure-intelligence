"""Membership-scoped identity read tests (P1-A1).

These tests cover the plan's acceptance criterion "a user without a
membership sees no organization data" at the server-side read path
(``app.services.identity``). There is no HTTP route yet; the same
helpers will gate the routes introduced in later lots.

Same SQLite notes as test_identity_models.py: in-memory database,
foreign keys enforced, no PostgreSQL required.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.identity import Membership, Organization, User
from app.services.identity import (
    get_organization_for_user,
    list_organizations_for_user,
)


@pytest.fixture()
def db() -> Session:
    """Fresh in-memory database with foreign keys enforced."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):  # noqa: ANN001, ANN202
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_org(db: Session, name: str, slug: str) -> Organization:
    org = Organization(name=name, slug=slug)
    db.add(org)
    db.commit()
    return org


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@")[0])
    db.add(user)
    db.commit()
    return user


def _add_member(db: Session, org: Organization, user: User, role: str) -> None:
    db.add(Membership(organization_id=org.id, user_id=user.id, role=role))
    db.commit()


def test_user_without_membership_sees_nothing(db: Session) -> None:
    """A user with no membership sees no organization at all."""
    org = _make_org(db, "Acme Corp", "acme")
    stranger = _make_user(db, "stranger@example.com")
    assert list_organizations_for_user(db, stranger.id) == []
    assert get_organization_for_user(db, stranger.id, org.id) is None


def test_user_with_membership_sees_its_organization(db: Session) -> None:
    """A member sees exactly the organizations they belong to."""
    org = _make_org(db, "Acme Corp", "acme")
    alice = _make_user(db, "alice@example.com")
    _add_member(db, org, alice, "owner")
    visible = list_organizations_for_user(db, alice.id)
    assert [o.id for o in visible] == [org.id]
    assert get_organization_for_user(db, alice.id, org.id) is not None


def test_user_does_not_see_other_organizations(db: Session) -> None:
    """Membership in org A gives no visibility into org B (cross-tenant)."""
    org_a = _make_org(db, "Org A", "org-a")
    org_b = _make_org(db, "Org B", "org-b")
    alice = _make_user(db, "alice@example.com")
    bob = _make_user(db, "bob@example.com")
    _add_member(db, org_a, alice, "member")
    _add_member(db, org_b, bob, "member")

    assert [o.id for o in list_organizations_for_user(db, alice.id)] == [org_a.id]
    assert [o.id for o in list_organizations_for_user(db, bob.id)] == [org_b.id]
    assert get_organization_for_user(db, alice.id, org_b.id) is None
    assert get_organization_for_user(db, bob.id, org_a.id) is None


def test_soft_deleted_organization_not_visible(db: Session) -> None:
    """A soft-deleted organization disappears from membership reads."""
    org = _make_org(db, "Acme Corp", "acme")
    alice = _make_user(db, "alice@example.com")
    _add_member(db, org, alice, "owner")
    assert list_organizations_for_user(db, alice.id) != []

    org.deleted_at = datetime.now(timezone.utc)
    db.commit()

    assert list_organizations_for_user(db, alice.id) == []
    assert get_organization_for_user(db, alice.id, org.id) is None


def test_user_member_of_two_organizations_sees_both(db: Session) -> None:
    """Memberships are per organization; a user can belong to several."""
    org_a = _make_org(db, "Org A", "org-a")
    org_b = _make_org(db, "Org B", "org-b")
    alice = _make_user(db, "alice@example.com")
    _add_member(db, org_a, alice, "member")
    _add_member(db, org_b, alice, "admin")
    visible = list_organizations_for_user(db, alice.id)
    assert {o.id for o in visible} == {org_a.id, org_b.id}
