"""Read-only organization API protected by session and tenant-scoped RBAC."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.authorization import get_current_user, require_organization_permission
from app.db.session import get_db
from app.models.identity import Membership, Organization, User
from app.models.rbac import Role
from app.services.identity import list_organizations_for_user
from app.services.rbac import user_has_permission

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


class OrganizationResponse(BaseModel):
    """Safe organization fields visible to an active member."""

    id: UUID
    name: str
    slug: str
    created_at: datetime


class MemberResponse(BaseModel):
    """Safe member identity and organization-local role."""

    user_id: UUID
    email: str
    display_name: str
    role: str
    joined_at: datetime


class RoleResponse(BaseModel):
    """Organization-local role and its named capabilities."""

    id: UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[OrganizationResponse]:
    """List only active memberships for which organization.read is granted."""
    organizations = list_organizations_for_user(db, current_user.id)
    return [
        OrganizationResponse(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            created_at=organization.created_at,
        )
        for organization in organizations
        if user_has_permission(
            db,
            current_user.id,
            organization.id,
            "organization.read",
        )
    ]


@router.get("/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization: Organization = Depends(
        require_organization_permission("organization.read")
    ),
) -> OrganizationResponse:
    """Read one organization after membership and permission checks."""
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        created_at=organization.created_at,
    )


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
def list_organization_members(
    organization: Organization = Depends(
        require_organization_permission("members.read")
    ),
    db: Session = Depends(get_db),
) -> list[MemberResponse]:
    """List active, non-deleted users belonging to the selected organization."""
    statement = (
        select(
            User.id,
            User.email,
            User.display_name,
            Role.name,
            Membership.created_at,
        )
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .join(
            Role,
            and_(
                Role.id == Membership.role_id,
                Role.organization_id == Membership.organization_id,
            ),
        )
        .where(Membership.organization_id == organization.id)
        .where(User.is_active.is_(True))
        .where(User.deleted_at.is_(None))
        .order_by(User.email)
    )
    rows = db.execute(statement).all()
    return [
        MemberResponse(
            user_id=row[0],
            email=row[1],
            display_name=row[2],
            role=row[3],
            joined_at=row[4],
        )
        for row in rows
    ]


@router.get("/{organization_id}/roles", response_model=list[RoleResponse])
def list_organization_roles(
    organization: Organization = Depends(require_organization_permission("roles.read")),
    db: Session = Depends(get_db),
) -> list[RoleResponse]:
    """List roles and permissions only within the authorized organization."""
    roles = db.scalars(
        select(Role).where(Role.organization_id == organization.id).order_by(Role.name)
    ).all()
    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            is_system=role.is_system,
            permissions=sorted(permission.name for permission in role.permissions),
        )
        for role in roles
    ]
