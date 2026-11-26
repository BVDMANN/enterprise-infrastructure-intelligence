"""RBAC service and tenant-boundary tests (P1-A3)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.identity import Membership, Organization, User
from app.models.rbac import Permission, Role
from app.services.rbac import (
    PermissionDenied,
    create_default_roles_for_organization,
    list_user_permissions,
    require_permission,
    user_has_permission,
)


@pytest.fixture()
def db() -> Session:
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


def _organization(db: Session, slug: str) -> Organization:
    organization = Organization(name=slug.title(), slug=slug)
    db.add(organization)
    db.commit()
    return organization


def _user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@")[0])
    db.add(user)
    db.commit()
    return user


def _role(db: Session, organization: Organization, name: str) -> Role:
    role = Role(organization_id=organization.id, name=name, is_system=True)
    db.add(role)
    db.flush()
    return role


def _membership(
    db: Session, organization: Organization, user: User, role: Role
) -> None:
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role_id=role.id,
        )
    )
    db.commit()


def test_default_role_provisioning_is_idempotent(db: Session) -> None:
    organization = _organization(db, "acme")
    first = create_default_roles_for_organization(db, organization.id)
    db.commit()
    second = create_default_roles_for_organization(db, organization.id)
    db.commit()
    assert {role.name for role in first} == {
        "owner",
        "admin",
        "member",
        "viewer",
    }
    assert {role.name for role in second} == {
        "owner",
        "admin",
        "member",
        "viewer",
    }
    assert db.query(Role).filter_by(organization_id=organization.id).count() == 4


def test_owner_can_manage_infrastructure(db: Session) -> None:
    organization = _organization(db, "acme")
    user = _user(db, "owner@example.com")
    roles = create_default_roles_for_organization(db, organization.id)
    db.flush()
    owner = next(role for role in roles if role.name == "owner")
    _membership(db, organization, user, owner)
    assert user_has_permission(
        db, user.id, organization.id, "infrastructure.manage"
    )
    assert "roles.manage" in list_user_permissions(db, user.id, organization.id)
    require_permission(db, user.id, organization.id, "infrastructure.manage")


def test_viewer_can_read_but_cannot_manage_members(db: Session) -> None:
    organization = _organization(db, "acme")
    user = _user(db, "viewer@example.com")
    roles = create_default_roles_for_organization(db, organization.id)
    db.flush()
    viewer = next(role for role in roles if role.name == "viewer")
    _membership(db, organization, user, viewer)
    assert user_has_permission(
        db, user.id, organization.id, "infrastructure.read"
    )
    assert not user_has_permission(
        db, user.id, organization.id, "members.manage"
    )
    with pytest.raises(PermissionDenied):
        require_permission(db, user.id, organization.id, "members.manage")


def test_user_without_membership_has_no_permissions(db: Session) -> None:
    organization = _organization(db, "acme")
    user = _user(db, "stranger@example.com")
    create_default_roles_for_organization(db, organization.id)
    db.commit()
    assert list_user_permissions(db, user.id, organization.id) == set()


def test_inactive_or_deleted_user_has_no_permissions(db: Session) -> None:
    organization = _organization(db, "acme")
    user = _user(db, "inactive@example.com")
    roles = create_default_roles_for_organization(db, organization.id)
    db.flush()
    _membership(
        db, organization, user, next(r for r in roles if r.name == "owner")
    )
    user.is_active = False
    db.commit()
    assert list_user_permissions(db, user.id, organization.id) == set()
    user.is_active = True
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert list_user_permissions(db, user.id, organization.id) == set()


def test_deleted_organization_has_no_permissions(db: Session) -> None:
    organization = _organization(db, "acme")
    user = _user(db, "owner@example.com")
    roles = create_default_roles_for_organization(db, organization.id)
    db.flush()
    _membership(db, organization, user, next(r for r in roles if r.name == "owner"))
    organization.deleted_at = datetime.now(timezone.utc)
    db.commit()
    assert list_user_permissions(db, user.id, organization.id) == set()


def test_role_from_another_tenant_cannot_be_assigned(db: Session) -> None:
    organization_a = _organization(db, "org-a")
    organization_b = _organization(db, "org-b")
    user = _user(db, "alice@example.com")
    role_a = _role(db, organization_a, "admin")
    db.commit()
    db.add(
        Membership(
            organization_id=organization_b.id,
            user_id=user.id,
            role_id=role_a.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_custom_role_cannot_be_overwritten_by_default_provisioning(db: Session) -> None:
    organization = _organization(db, "acme")
    db.add(
        Role(
            organization_id=organization.id,
            name="owner",
            description="Custom role",
            is_system=False,
        )
    )
    db.commit()
    with pytest.raises(ValueError, match="reserved"):
        create_default_roles_for_organization(db, organization.id)


def test_permission_catalog_has_unique_names(db: Session) -> None:
    db.add(Permission(name="infrastructure.read", description="Read infrastructure"))
    db.commit()
    db.add(Permission(name="infrastructure.read", description="Duplicate"))
    with pytest.raises(IntegrityError):
        db.commit()
