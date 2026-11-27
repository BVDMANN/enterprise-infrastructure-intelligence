"""Organization provisioning — creation and slug validation (P1-A1 completion).

The single creation entry point used by the HTTP route and by the
bootstrap script: an organization is created together with its four
system roles and the creator's owner membership, in one transaction,
and the creation is audited. The caller owns the transaction
commit/rollback, like every other service in this codebase.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import Membership, Organization, User
from app.services.audit import record_audit_event
from app.services.rbac import create_default_roles_for_organization

#: Slugs are lowercase, hyphen-separated, no leading/trailing hyphen.
#: Same rule as the bootstrap script (scripts/bootstrap_admin.py).
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
MAX_NAME_LENGTH = 255
MAX_SLUG_LENGTH = 255


class OrganizationValidationError(ValueError):
    """Invalid organization name or slug (mapped to HTTP 422)."""


class OrganizationSlugConflictError(ValueError):
    """The slug is already taken by another organization (HTTP 409)."""


class OrganizationActorInactiveError(PermissionError):
    """The creator became inactive before organization creation acquired its lock."""


def normalize_slug(value: str) -> str:
    """Lowercase a slug without surrounding whitespace."""
    return value.strip().lower()


def validate_slug(value: str) -> str:
    """Normalize and validate a slug, or raise OrganizationValidationError."""
    slug = normalize_slug(value)
    if not slug or len(slug) > MAX_SLUG_LENGTH or not SLUG_PATTERN.fullmatch(slug):
        raise OrganizationValidationError(
            "Slug must be lowercase, hyphen-separated (a-z, 0-9, '-') "
            "and at most 255 characters"
        )
    return slug


def validate_organization_name(value: str) -> str:
    """Strip and validate an organization name."""
    name = value.strip()
    if not name or len(name) > MAX_NAME_LENGTH:
        raise OrganizationValidationError(
            "Organization name is required (max 255 characters)"
        )
    return name


def create_organization(
    db: Session, *, creator: User, name: str, slug: str
) -> Organization:
    """Create an organization, its system roles and the creator's owner membership.

    The caller owns the transaction: nothing is committed here. A
    concurrent creation with the same slug is rejected by the database
    unique constraint (the router maps the IntegrityError to 409).
    """
    validated_name = validate_organization_name(name)
    validated_slug = validate_slug(slug)

    locked_creator = db.scalar(
        select(User)
        .where(User.id == creator.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        locked_creator is None
        or not locked_creator.is_active
        or locked_creator.deleted_at is not None
    ):
        raise OrganizationActorInactiveError("Creator account is not active")
    creator = locked_creator

    existing = db.scalar(
        select(Organization.id).where(Organization.slug == validated_slug)
    )
    if existing is not None:
        raise OrganizationSlugConflictError(
            "An organization with this slug already exists"
        )

    organization = Organization(name=validated_name, slug=validated_slug)
    db.add(organization)
    db.flush()

    roles = create_default_roles_for_organization(db, organization.id)
    owner_role = next((role for role in roles if role.name == "owner"), None)
    if owner_role is None:  # pragma: no cover - roles are always created
        raise OrganizationValidationError("System owner role was not created")

    db.add(
        Membership(
            organization_id=organization.id,
            user_id=creator.id,
            role_id=owner_role.id,
        )
    )
    db.flush()

    record_audit_event(
        db,
        organization_id=organization.id,
        actor_user_id=creator.id,
        event_type="organization.created",
        target_type="organization",
        target_id=str(organization.id),
        details={"name": validated_name, "slug": validated_slug},
    )
    return organization
