"""Organization API protected by session and tenant-scoped RBAC."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import (
    get_current_user,
    require_organization_permission,
    require_session_csrf,
)
from app.db.session import get_db
from app.models.identity import Invitation, Membership, Organization, User
from app.models.rbac import Role
from app.services.audit import list_audit_events, record_audit_event
from app.services.identity import list_organizations_for_user
from app.services.invitations import (
    InvitationConflictError,
    InvitationNotFoundError,
    InvitationValidationError,
    create_invitation,
    invitation_status,
    revoke_invitation,
)
from app.services.organizations import (
    OrganizationActorInactiveError,
    OrganizationSlugConflictError,
    OrganizationValidationError,
    create_organization as create_organization_service,
    validate_organization_name,
)
from app.services.rbac import user_has_permission

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


class OrganizationResponse(BaseModel):
    """Safe organization fields visible to an active member."""

    id: UUID
    name: str
    slug: str
    created_at: datetime


class MemberResponse(BaseModel):
    """Safe membership identity, role identifier and organization-local role."""

    membership_id: UUID
    user_id: UUID
    role_id: UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    joined_at: datetime


class OrganizationCreateRequest(BaseModel):
    """Create an organization; the creator becomes its Organization Owner."""

    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)


class OrganizationUpdateRequest(BaseModel):
    """Rename an organization; the slug is immutable once created."""

    name: str = Field(min_length=1, max_length=255)


class MemberStatusRequest(BaseModel):
    """Deactivate (false) or reactivate (true) a member's user account."""

    is_active: bool


class InvitationCreateRequest(BaseModel):
    """Invite one email to join the organization with one role."""

    email: str = Field(min_length=3, max_length=320)
    role_id: UUID
    expires_in_days: int = Field(default=7, ge=1, le=30)


class InvitationResponse(BaseModel):
    """A member invitation, without its token (never returned after creation)."""

    id: UUID
    organization_id: UUID
    email: str
    role_id: UUID
    role_name: str
    status: str
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


class InvitationCreateResponse(InvitationResponse):
    """Creation response: the token is returned exactly once, with its link."""

    token: str
    accept_path: str


class MembershipCreateRequest(BaseModel):
    """Add an existing active user to an organization with a local role."""

    user_id: UUID
    role_id: UUID


class MembershipResponse(BaseModel):
    """Safe identifiers and creation time for an organization membership."""

    id: UUID
    user_id: UUID
    role_id: UUID
    created_at: datetime


class MembershipUpdateRequest(BaseModel):
    """Move an existing membership to another role in the same organization."""

    role_id: UUID


class RoleResponse(BaseModel):
    """Organization-local role and its named capabilities."""

    id: UUID
    name: str
    description: str | None
    is_system: bool
    permissions: list[str]


class AuditEventResponse(BaseModel):
    """Safe tenant-scoped audit event returned to authorized readers."""

    id: UUID
    organization_id: UUID
    actor_user_id: UUID
    event_type: str
    target_type: str | None
    target_id: str | None
    request_id: str | None
    details: dict[str, Any]
    occurred_at: datetime


def _lock_organization_for_membership_mutation(
    db: Session, organization_id: UUID
) -> None:
    """Serialize membership writes for one tenant on databases with row locks."""
    db.scalar(
        select(Organization.id)
        .where(Organization.id == organization_id)
        .with_for_update()
    )


def _lock_user_for_membership_mutation(db: Session, user_id: UUID) -> User | None:
    """Serialize account-wide status changes with every membership creation path."""
    return db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _active_owner_membership_count(
    db: Session,
    organization_id: UUID,
    *,
    excluding_membership_id: UUID | None = None,
) -> int:
    """Count only owner memberships belonging to active, non-deleted users."""
    statement = (
        select(func.count(Membership.id))
        .select_from(Membership)
        .join(User, User.id == Membership.user_id)
        .join(
            Role,
            and_(
                Role.id == Membership.role_id,
                Role.organization_id == Membership.organization_id,
            ),
        )
        .where(Membership.organization_id == organization_id)
        .where(Role.name == "owner")
        .where(User.is_active.is_(True))
        .where(User.deleted_at.is_(None))
    )
    if excluding_membership_id is not None:
        statement = statement.where(Membership.id != excluding_membership_id)
    return int(db.scalar(statement) or 0)


def _prevent_removing_last_active_owner(
    db: Session,
    organization_id: UUID,
    membership: Membership,
    current_role: Role,
    target_user: User | None,
) -> None:
    """Keep at least one active owner while demoting or removing a membership."""
    if (
        current_role.name != "owner"
        or target_user is None
        or not target_user.is_active
        or target_user.deleted_at is not None
    ):
        return
    if (
        _active_owner_membership_count(
            db,
            organization_id,
            excluding_membership_id=membership.id,
        )
        == 0
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization must retain at least one active owner",
        )


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


@router.post(
    "", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED
)
def create_organization(
    payload: OrganizationCreateRequest,
    actor: User = Depends(get_current_user),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Create an organization; the creator becomes its Organization Owner.

    Session + CSRF only: the creator has no membership yet, so no
    organization permission can be required here. The organization,
    its four system roles and the owner membership are created in one
    transaction and the creation is audited.
    """
    try:
        organization = create_organization_service(
            db, creator=actor, name=payload.name, slug=payload.slug
        )
        db.commit()
    except OrganizationActorInactiveError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except OrganizationSlugConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except OrganizationValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except IntegrityError:
        # Concurrent creation with the same slug: the database unique
        # constraint is the final arbiter.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An organization with this slug already exists",
        ) from None
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        created_at=organization.created_at,
    )


@router.patch("/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    payload: OrganizationUpdateRequest,
    organization: Organization = Depends(
        require_organization_permission("organization.manage")
    ),
    actor: User = Depends(get_current_user),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> OrganizationResponse:
    """Rename an organization. The slug is immutable once created."""
    try:
        new_name = validate_organization_name(payload.name)
    except OrganizationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if new_name != organization.name:
        previous_name = organization.name
        organization.name = new_name
        db.flush()
        record_audit_event(
            db,
            organization_id=organization.id,
            actor_user_id=actor.id,
            event_type="organization.updated",
            target_type="organization",
            target_id=str(organization.id),
            details={"previous_name": previous_name, "name": new_name},
        )
        db.commit()
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        slug=organization.slug,
        created_at=organization.created_at,
    )


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    organization: Organization = Depends(
        require_organization_permission("organization.manage")
    ),
    actor: User = Depends(get_current_user),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> Response:
    """Soft delete an organization (owner only, audited).

    The audit event is recorded before marking the organization
    deleted: the audit writer refuses actors of a deleted
    organization. Memberships and audit history are preserved.
    """
    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=actor.id,
        event_type="organization.deleted",
        target_type="organization",
        target_id=str(organization.id),
        details={"name": organization.name, "slug": organization.slug},
    )
    organization.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{organization_id}/members", response_model=list[MemberResponse])
def list_organization_members(
    organization: Organization = Depends(
        require_organization_permission("members.read")
    ),
    include_inactive: bool = Query(
        default=False,
        description="Include deactivated members (their is_active is false).",
    ),
    db: Session = Depends(get_db),
) -> list[MemberResponse]:
    """List members of an organization, including their role name.

    By default only active members are returned (the behavior of the
    P1-A1 initial delivery). With ``include_inactive`` the list also
    covers deactivated accounts, which administrators need to
    reactivate them.
    """
    user_conditions = [User.deleted_at.is_(None)]
    if not include_inactive:
        user_conditions.append(User.is_active.is_(True))

    statement = (
        select(
            Membership.id,
            User.id,
            Role.id,
            User.email,
            User.display_name,
            Role.name,
            User.is_active,
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
        .where(*user_conditions)
        .order_by(User.email)
    )
    rows = db.execute(statement).all()
    return [
        MemberResponse(
            membership_id=row[0],
            user_id=row[1],
            role_id=row[2],
            email=row[3],
            display_name=row[4],
            role=row[5],
            is_active=row[6],
            joined_at=row[7],
        )
        for row in rows
    ]


@router.post(
    "/{organization_id}/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_membership(
    payload: MembershipCreateRequest,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("members.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    """Add an existing user and append the audit event in the same transaction."""
    _lock_organization_for_membership_mutation(db, organization.id)
    target_user = _lock_user_for_membership_mutation(db, payload.user_id)
    if (
        target_user is None
        or not target_user.is_active
        or target_user.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active user not found",
        )

    role = db.scalar(
        select(Role)
        .where(Role.id == payload.role_id)
        .where(Role.organization_id == organization.id)
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found in organization",
        )

    existing_membership = db.scalar(
        select(Membership.id)
        .where(Membership.organization_id == organization.id)
        .where(Membership.user_id == target_user.id)
    )
    if existing_membership is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization",
        )

    membership = Membership(
        organization_id=organization.id,
        user_id=target_user.id,
        role_id=role.id,
    )
    db.add(membership)
    db.flush()

    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=actor.id,
        event_type="membership.created",
        target_type="membership",
        target_id=str(membership.id),
        details={
            "target_user_id": str(target_user.id),
            "role_id": str(role.id),
            "role_name": role.name,
        },
    )
    response = MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        role_id=membership.role_id,
        created_at=membership.created_at,
    )
    db.commit()
    return response


@router.patch(
    "/{organization_id}/memberships/{membership_id}",
    response_model=MembershipResponse,
)
def update_organization_membership(
    payload: MembershipUpdateRequest,
    membership_id: UUID,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("members.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> MembershipResponse:
    """Change a tenant-local role and append its audit event atomically."""
    _lock_organization_for_membership_mutation(db, organization.id)
    membership = db.scalar(
        select(Membership)
        .where(Membership.id == membership_id)
        .where(Membership.organization_id == organization.id)
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )

    target_user = db.get(User, membership.user_id)
    if (
        target_user is None
        or not target_user.is_active
        or target_user.deleted_at is not None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active member not found",
        )

    current_role = db.scalar(
        select(Role)
        .where(Role.id == membership.role_id)
        .where(Role.organization_id == organization.id)
    )
    if current_role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership role is invalid for this organization",
        )

    new_role = db.scalar(
        select(Role)
        .where(Role.id == payload.role_id)
        .where(Role.organization_id == organization.id)
    )
    if new_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found in organization",
        )

    if current_role.id == new_role.id:
        return MembershipResponse(
            id=membership.id,
            user_id=membership.user_id,
            role_id=membership.role_id,
            created_at=membership.created_at,
        )

    if current_role.name == "owner" and new_role.name != "owner":
        _prevent_removing_last_active_owner(
            db,
            organization.id,
            membership,
            current_role,
            target_user,
        )

    previous_role_id = str(current_role.id)
    previous_role_name = current_role.name
    membership.role_id = new_role.id
    db.flush()

    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=actor.id,
        event_type="membership.role_changed",
        target_type="membership",
        target_id=str(membership.id),
        details={
            "target_user_id": str(target_user.id),
            "previous_role_id": previous_role_id,
            "previous_role_name": previous_role_name,
            "role_id": str(new_role.id),
            "role_name": new_role.name,
        },
    )
    response = MembershipResponse(
        id=membership.id,
        user_id=membership.user_id,
        role_id=membership.role_id,
        created_at=membership.created_at,
    )
    db.commit()
    return response


@router.delete(
    "/{organization_id}/memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_organization_membership(
    membership_id: UUID,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("members.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> Response:
    """Remove a tenant membership and append its audit event atomically."""
    _lock_organization_for_membership_mutation(db, organization.id)
    membership = db.scalar(
        select(Membership)
        .where(Membership.id == membership_id)
        .where(Membership.organization_id == organization.id)
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    if membership.user_id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A member cannot remove their own membership",
        )

    current_role = db.scalar(
        select(Role)
        .where(Role.id == membership.role_id)
        .where(Role.organization_id == organization.id)
    )
    if current_role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership role is invalid for this organization",
        )
    target_user = db.get(User, membership.user_id)
    _prevent_removing_last_active_owner(
        db,
        organization.id,
        membership,
        current_role,
        target_user,
    )

    membership_id_value = str(membership.id)
    target_user_id = str(membership.user_id)
    role_id = str(current_role.id)
    role_name = current_role.name
    db.delete(membership)
    db.flush()

    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=actor.id,
        event_type="membership.deleted",
        target_type="membership",
        target_id=membership_id_value,
        details={
            "target_user_id": target_user_id,
            "role_id": role_id,
            "role_name": role_name,
        },
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{organization_id}/members/{membership_id}/status",
    response_model=MemberResponse,
)
def update_member_status(
    payload: MemberStatusRequest,
    membership_id: UUID,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("members.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> MemberResponse:
    """Deactivate or reactivate a member's user account.

    The status is account-wide, so it is refused when the target has an
    active membership in another organization. Use tenant-scoped membership
    removal to revoke access in only one organization. The actor's own account
    and the last active Organization Owner are also protected. Idempotent.
    """
    _lock_organization_for_membership_mutation(db, organization.id)
    membership = db.scalar(
        select(Membership)
        .where(Membership.id == membership_id)
        .where(Membership.organization_id == organization.id)
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    if membership.user_id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A member cannot change their own status",
        )

    current_role = db.scalar(
        select(Role)
        .where(Role.id == membership.role_id)
        .where(Role.organization_id == organization.id)
    )
    if current_role is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Membership role is invalid for this organization",
        )
    target_user = _lock_user_for_membership_mutation(db, membership.user_id)
    if target_user is None or target_user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active member not found",
        )
    if target_user.is_active == payload.is_active:
        return MemberResponse(
            membership_id=membership.id,
            user_id=target_user.id,
            role_id=membership.role_id,
            email=target_user.email,
            display_name=target_user.display_name,
            role=current_role.name,
            is_active=target_user.is_active,
            joined_at=membership.created_at,
        )

    other_active_membership = db.scalar(
        select(Membership.id)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(Membership.user_id == target_user.id)
        .where(Membership.organization_id != organization.id)
        .where(Organization.deleted_at.is_(None))
        .limit(1)
    )
    if other_active_membership is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Account-wide status cannot be changed while the user belongs "
                "to another organization"
            ),
        )

    if not payload.is_active:
        _prevent_removing_last_active_owner(
            db,
            organization.id,
            membership,
            current_role,
            target_user,
        )

    target_user.is_active = payload.is_active
    db.flush()
    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=actor.id,
        event_type=(
            "user.deactivated" if not payload.is_active else "user.reactivated"
        ),
        target_type="user",
        target_id=str(target_user.id),
        details={
            "target_user_id": str(target_user.id),
            "membership_id": str(membership.id),
        },
    )
    db.commit()
    return MemberResponse(
        membership_id=membership.id,
        user_id=target_user.id,
        role_id=membership.role_id,
        email=target_user.email,
        display_name=target_user.display_name,
        role=current_role.name,
        is_active=target_user.is_active,
        joined_at=membership.created_at,
    )


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


@router.get(
    "/{organization_id}/audit-events",
    response_model=list[AuditEventResponse],
)
def list_organization_audit_events(
    organization: Organization = Depends(require_organization_permission("audit.read")),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[AuditEventResponse]:
    """List append-only events after session, membership and audit.read checks."""
    events = list_audit_events(db, organization.id, limit=limit)
    return [
        AuditEventResponse(
            id=item.id,
            organization_id=item.organization_id,
            actor_user_id=item.actor_user_id,
            event_type=item.event_type,
            target_type=item.target_type,
            target_id=item.target_id,
            request_id=item.request_id,
            details=item.details,
            occurred_at=item.occurred_at,
        )
        for item in events
    ]


def _invitation_response(
    invitation: Invitation, *, role_name: str
) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        organization_id=invitation.organization_id,
        email=invitation.email,
        role_id=invitation.role_id,
        role_name=role_name,
        status=invitation_status(invitation),
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
    )


@router.post(
    "/{organization_id}/invitations",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_invitation(
    payload: InvitationCreateRequest,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("members.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> InvitationCreateResponse:
    """Invite one email to join the organization with one role.

    The token is returned exactly once in this response (with its
    accept path); it is never stored in clear and never returned
    again. No email is sent in PHASE 1: the inviter copies the accept
    link manually.
    """
    try:
        invitation, token = create_invitation(
            db,
            inviter=actor,
            organization=organization,
            email=payload.email,
            role_id=payload.role_id,
            expires_in_days=payload.expires_in_days,
        )
        role = db.scalar(select(Role).where(Role.id == invitation.role_id))
        role_name = role.name if role is not None else "unknown"
        db.commit()
    except InvitationNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except InvitationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except InvitationValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    base = _invitation_response(invitation, role_name=role_name)
    return InvitationCreateResponse(
        **base.model_dump(),
        token=token,
        accept_path=f"/invitations/{token}",
    )


@router.get(
    "/{organization_id}/invitations",
    response_model=list[InvitationResponse],
)
def list_organization_invitations(
    organization: Organization = Depends(
        require_organization_permission("members.read")
    ),
    db: Session = Depends(get_db),
) -> list[InvitationResponse]:
    """List the organization's invitations with their computed status."""
    invitations = db.scalars(
        select(Invitation)
        .where(Invitation.organization_id == organization.id)
        .order_by(Invitation.created_at.desc())
    ).all()
    roles = {
        role.id: role.name
        for role in db.scalars(
            select(Role).where(Role.organization_id == organization.id)
        ).all()
    }
    return [
        _invitation_response(
            invitation, role_name=roles.get(invitation.role_id, "unknown")
        )
        for invitation in invitations
    ]


@router.delete(
    "/{organization_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_organization_invitation(
    invitation_id: UUID,
    actor: User = Depends(get_current_user),
    organization: Organization = Depends(
        require_organization_permission("members.manage")
    ),
    _csrf: None = Depends(require_session_csrf),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke an invitation. Revoking an already revoked invitation is a no-op."""
    # Match the acceptance path's row lock. After waiting, PostgreSQL
    # returns the committed terminal state instead of a stale pending object.
    invitation = db.scalar(
        select(Invitation)
        .where(Invitation.id == invitation_id)
        .where(Invitation.organization_id == organization.id)
        .with_for_update()
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )
    try:
        revoke_invitation(
            db, actor=actor, organization=organization, invitation=invitation
        )
        db.commit()
    except InvitationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
