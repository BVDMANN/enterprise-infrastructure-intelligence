"""Membership-scoped identity reads (P1-A1).

No public HTTP route exists yet — P1-A1 exposes no endpoint. These
helpers are the server-side read path that later routes will use: a
user only ever sees organizations they are a member of, and
soft-deleted organizations are never returned. The tenant is derived
from the membership, never from a value supplied by the caller alone.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.identity import Membership, Organization


def list_organizations_for_user(db: Session, user_id: uuid.UUID) -> list[Organization]:
    """Organizations the user is a member of, excluding soft-deleted ones.

    A user without any membership sees nothing.
    """
    stmt = (
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user_id)
        .where(Organization.deleted_at.is_(None))
        .order_by(Organization.name)
    )
    return list(db.scalars(stmt).all())


def get_organization_for_user(
    db: Session, user_id: uuid.UUID, organization_id: uuid.UUID
) -> Organization | None:
    """One organization, only if the user is a member and it is not soft-deleted.

    Returns ``None`` when the user has no membership in the organization
    (including when the organization belongs to another tenant).
    """
    stmt = (
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user_id)
        .where(Organization.id == organization_id)
        .where(Organization.deleted_at.is_(None))
    )
    return db.scalars(stmt).one_or_none()
