"""Server-side permission resolution and default role provisioning (P1-A3)."""

from __future__ import annotations

import uuid

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.identity import Membership, Organization, User
from app.models.rbac import Permission, Role, RolePermission


PERMISSION_DESCRIPTIONS = {
    "organization.read": "Read the current organization's profile.",
    "organization.manage": "Change organization-level settings.",
    "members.read": "Read organization members and memberships.",
    "members.manage": "Invite, add, deactivate, or remove organization members.",
    "roles.read": "Read organization roles and permission assignments.",
    "roles.manage": "Create and change organization-scoped roles.",
    "infrastructure.read": "Read infrastructure inventory and status.",
    "infrastructure.manage": "Manage infrastructure connectors and inventory.",
    "audit.read": "Read the organization's audit events.",
}

DEFAULT_ROLE_PERMISSIONS = {
    "owner": frozenset(PERMISSION_DESCRIPTIONS),
    "admin": frozenset(
        {
            "organization.read",
            "members.read",
            "members.manage",
            "roles.read",
            "roles.manage",
            "infrastructure.read",
            "infrastructure.manage",
            "audit.read",
        }
    ),
    "member": frozenset(
        {"organization.read", "members.read", "infrastructure.read"}
    ),
    "viewer": frozenset(
        {"organization.read", "infrastructure.read", "audit.read"}
    ),
}


class PermissionDenied(PermissionError):
    """Raised when an authenticated user lacks a named organization permission."""


def create_default_roles_for_organization(
    db: Session, organization_id: uuid.UUID
) -> list[Role]:
    """Create missing system roles and the permission catalog for one tenant.

    The caller owns the transaction. Existing system roles are left unchanged;
    a custom role using a reserved built-in name is rejected rather than
    silently overwritten.
    """
    organization = db.get(Organization, organization_id)
    if organization is None or organization.deleted_at is not None:
        raise ValueError("Organization does not exist or is deleted")

    permissions: dict[str, Permission] = {}
    for name, description in PERMISSION_DESCRIPTIONS.items():
        permission = db.scalar(select(Permission).where(Permission.name == name))
        if permission is None:
            permission = Permission(name=name, description=description)
            db.add(permission)
            db.flush()
        permissions[name] = permission

    roles: list[Role] = []
    for name, permission_names in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.scalar(
            select(Role).where(
                Role.organization_id == organization_id,
                Role.name == name,
            )
        )
        if role is not None:
            if not role.is_system:
                raise ValueError(f"Role name {name!r} is reserved for a system role")
            roles.append(role)
            continue

        role = Role(
            organization_id=organization_id,
            name=name,
            description=f"Built-in {name} role",
            is_system=True,
        )
        db.add(role)
        db.flush()
        for permission_name in sorted(permission_names):
            db.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permissions[permission_name].id,
                )
            )
        roles.append(role)

    db.flush()
    return roles


def list_user_permissions(
    db: Session, user_id: uuid.UUID, organization_id: uuid.UUID
) -> set[str]:
    """Resolve permissions from the user's active membership in one tenant."""
    statement = (
        select(Permission.name)
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .join(Organization, Organization.id == Membership.organization_id)
        .join(
            Role,
            and_(
                Role.id == Membership.role_id,
                Role.organization_id == Membership.organization_id,
            ),
        )
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(Membership.user_id == user_id)
        .where(Membership.organization_id == organization_id)
        .where(User.is_active.is_(True))
        .where(User.deleted_at.is_(None))
        .where(Organization.deleted_at.is_(None))
    )
    return set(db.scalars(statement).all())


def user_has_permission(
    db: Session,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permission_name: str,
) -> bool:
    """Return whether the active tenant membership grants a capability."""
    return permission_name in list_user_permissions(db, user_id, organization_id)


def require_permission(
    db: Session,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permission_name: str,
) -> None:
    """Fail closed when the active tenant membership lacks a capability."""
    if not user_has_permission(db, user_id, organization_id, permission_name):
        raise PermissionDenied("Permission denied")
