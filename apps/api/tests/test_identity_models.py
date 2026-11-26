"""Identity model tests (P1-A1).

Run against an in-memory SQLite database: the CI ``api`` job has no
PostgreSQL service, so the committed tests must pass without one. The
real PostgreSQL upgrade/downgrade of the migration is exercised by the
Compose smoke job (see .github/workflows/ci.yml).

Portability notes, verified by these tests:
- SQLite enforces foreign keys only with ``PRAGMA foreign_keys=ON``
  (enabled in the fixture); PostgreSQL enforces them by default.
- CITEXT is a PostgreSQL-only type: on SQLite the column is created
  as ``CITEXT`` (TEXT affinity, case-sensitive unique index). The
  case-insensitive email guarantee therefore relies on the Python
  normalization (strip + lowercase) as well as on CITEXT — both layers
  are tested here; on PostgreSQL they reinforce each other.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.identity import Membership, Organization, User


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


def _make_org(db: Session, slug: str = "acme") -> Organization:
    org = Organization(name="Acme Corp", slug=slug)
    db.add(org)
    db.commit()
    return org


def _make_user(
    db: Session, email: str = "alice@example.com", subject: str | None = "oidc-alice"
) -> User:
    user = User(email=email, display_name="Alice", oidc_subject=subject)
    db.add(user)
    db.commit()
    return user


def test_metadata_registers_identity_tables() -> None:
    """Importing app.models must register the three tables on Base.metadata."""
    assert set(Base.metadata.tables) >= {
        "organizations",
        "users",
        "memberships",
    }


def test_create_organization_defaults(db: Session) -> None:
    """A new organization gets a UUID, timestamps and no deleted_at."""
    org = _make_org(db)
    assert isinstance(org.id, uuid.UUID)
    assert org.created_at is not None
    assert org.updated_at is not None
    assert org.deleted_at is None


def test_organization_slug_unique(db: Session) -> None:
    """Two organizations cannot share a slug."""
    _make_org(db, slug="acme")
    db.add(Organization(name="Acme 2", slug="acme"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_organization_slug_normalized(db: Session) -> None:
    """Slugs are stored lowercase without surrounding whitespace."""
    org = _make_org(db, slug="  Acme-Corp ")
    assert org.slug == "acme-corp"
    # The normalized form collides with an existing slug.
    db.add(Organization(name="Other", slug="ACME-CORP"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_user_email_normalized(db: Session) -> None:
    """Emails are stored lowercase without surrounding whitespace."""
    user = _make_user(db, email="  Alice@Example.COM ")
    assert user.email == "alice@example.com"


def test_user_email_unique_case_insensitive(db: Session) -> None:
    """Two users cannot share an email, even with different casing."""
    _make_user(db, email="alice@example.com")
    db.add(User(email="ALICE@example.com", display_name="Alice 2"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_user_oidc_subject_unique(db: Session) -> None:
    """Two users cannot share an OIDC subject."""
    _make_user(db, subject="oidc-alice")
    db.add(
        User(
            email="bob@example.com",
            display_name="Bob",
            oidc_subject="oidc-alice",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_users_without_oidc_subject_allowed(db: Session) -> None:
    """NULL OIDC subjects are allowed (filled at first OIDC login, P1-A2)."""
    _make_user(db, email="alice@example.com", subject=None)
    _make_user(db, email="bob@example.com", subject=None)
    assert db.query(User).count() == 2


def test_user_defaults(db: Session) -> None:
    """New users are active, without MFA, and not soft-deleted."""
    user = _make_user(db)
    assert user.is_active is True
    assert user.mfa_enabled is False
    assert user.deleted_at is None


def test_membership_default_role(db: Session) -> None:
    """A membership without an explicit role defaults to member."""
    org = _make_org(db)
    user = _make_user(db)
    membership = Membership(organization_id=org.id, user_id=user.id)
    db.add(membership)
    db.commit()
    assert membership.role == "member"


def test_membership_unique_per_organization_and_user(db: Session) -> None:
    """A user holds at most one membership per organization."""
    org = _make_org(db)
    user = _make_user(db)
    db.add(Membership(organization_id=org.id, user_id=user.id, role="admin"))
    db.commit()
    db.add(Membership(organization_id=org.id, user_id=user.id, role="member"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_membership_requires_existing_organization(db: Session) -> None:
    """A membership cannot reference a missing organization."""
    user = _make_user(db)
    db.add(Membership(organization_id=uuid.uuid4(), user_id=user.id, role="member"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_membership_requires_existing_user(db: Session) -> None:
    """A membership cannot reference a missing user."""
    org = _make_org(db)
    db.add(Membership(organization_id=org.id, user_id=uuid.uuid4(), role="member"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_membership_invalid_role_rejected(db: Session) -> None:
    """Roles outside owner/admin/member/viewer are rejected by the CHECK."""
    org = _make_org(db)
    user = _make_user(db)
    db.add(Membership(organization_id=org.id, user_id=user.id, role="superuser"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_soft_delete_organization_keeps_rows(db: Session) -> None:
    """Soft delete marks the organization; memberships stay intact."""
    org = _make_org(db)
    user = _make_user(db)
    db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    org.deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert db.query(Organization).count() == 1
    assert db.query(Membership).count() == 1
    assert db.get(Organization, org.id) is not None


def test_soft_delete_user_keeps_rows(db: Session) -> None:
    """Soft delete marks the user; memberships stay intact."""
    org = _make_org(db)
    user = _make_user(db)
    db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert db.query(User).count() == 1
    assert db.query(Membership).count() == 1


def test_hard_delete_organization_with_memberships_restricted(
    db: Session,
) -> None:
    """RESTRICT: an organization with memberships cannot be hard-deleted."""
    org = _make_org(db)
    user = _make_user(db)
    db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    db.delete(org)
    with pytest.raises(IntegrityError):
        db.commit()


def test_hard_delete_user_with_memberships_restricted(db: Session) -> None:
    """RESTRICT: a user with memberships cannot be hard-deleted."""
    org = _make_org(db)
    user = _make_user(db)
    db.add(Membership(organization_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    db.delete(user)
    with pytest.raises(IntegrityError):
        db.commit()
