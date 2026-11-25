"""Identity models — organizations, users, memberships (P1-A1).

These are the tenant entities: every business row created in later lots
carries an ``organization_id`` that references ``organizations.id``.

Scope of this lot (PHASE1_PLAN.md P1-A1):
- models + Alembic migration + tests, no public HTTP route yet;
- ``organizations``: UUID, name, unique slug, timestamps, soft delete;
- ``users``: UUID, normalized/unique email, display name, unique OIDC
  subject, active status;
- ``memberships``: organization + user + role, unique
  (organization_id, user_id).

Decisions (documented, reversible in later lots):
- IDs are generated in Python (``uuid.uuid4``). The design document
  mentions ``gen_random_uuid()`` (PostgreSQL 13+ core, no extension
  needed), but a database-side default would make the schema untestable
  on SQLite and is unnecessary: the ORM always supplies the UUID.
- ``email`` uses CITEXT (installed by migration 0001) for
  case-insensitive uniqueness at the database level, and is also
  normalized in Python (strip + lowercase) so the guarantee holds on
  every backend and before the row reaches the database.
- ``oidc_subject`` is nullable: users exist before their first OIDC
  login (P1-A2 fills it). The uniqueness constraint still applies to
  non-NULL values.
- ``memberships.role`` is a plain string guarded by a CHECK constraint
  (owner/admin/member/viewer). There is no ``roles`` table yet — RBAC
  (P1-A3) replaces it with a ``role_id`` foreign key and may revise
  the set; the migration that does so must drop this CHECK first.
- ``organizations`` has no ``plan_id`` yet: the ``plans`` table does
  not exist (billing is a later lot). The foreign key is added with
  the plans table instead of forcing it into this lot.
- Soft delete (``deleted_at``) on organizations and users. A
  soft-deleted row is kept with its memberships (referential integrity
  preserved); membership-scoped reads exclude soft-deleted
  organizations (see ``app.services.identity``). Reusing the email of
  a soft-deleted user is blocked by the unique constraint until the
  row is hard-deleted — a deliberate conservative choice.
- Foreign keys use ON DELETE RESTRICT (design document §3): an
  organization or user with memberships cannot be hard-deleted.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.session import Base

#: Email column type: CITEXT on PostgreSQL (case-insensitive uniqueness
#: at the database level), plain String elsewhere. SQLAlchemy's
#: ``postgresql.CITEXT`` has no compiler for SQLite, so a Variant is
#: required for the tests to run without PostgreSQL; the Python
#: normalization (strip + lowercase) provides the same guarantee on
#: every backend.
EMAIL_TYPE = String().with_variant(CITEXT(), "postgresql")

#: Roles accepted on a membership until RBAC (P1-A3) replaces the
#: string role with a ``role_id`` foreign key.
MEMBERSHIP_ROLES = ("owner", "admin", "member", "viewer")


def _utcnow() -> datetime:
    """Current UTC time, used as the Python-side timestamp default."""
    return datetime.now(timezone.utc)


class Organization(Base):
    """A tenant. Every business row belongs to exactly one organization."""

    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organizations_slug"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", passive_deletes=True
    )

    @validates("slug")
    def _normalize_slug(self, key: str, value: str) -> str:
        """Slugs are stored lowercase without surrounding whitespace."""
        return value.strip().lower()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Organization(id={self.id!r}, slug={self.slug!r})"


class User(Base):
    """A person. Identity is the email; the OIDC subject is set at login."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("oidc_subject", name="uq_users_oidc_subject"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(EMAIL_TYPE, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    oidc_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", passive_deletes=True
    )

    @validates("email")
    def _normalize_email(self, key: str, value: str) -> str:
        """Emails are stored lowercase without surrounding whitespace."""
        return value.strip().lower()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"User(id={self.id!r}, email={self.email!r})"


class Membership(Base):
    """A user's membership in an organization, with a role.

    Uniqueness is (organization_id, user_id): a user holds at most one
    membership (and therefore one role) per organization.
    """

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_memberships_organization_user",
        ),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')",
            name="ck_memberships_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="member", server_default="member"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )

    organization: Mapped["Organization"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"Membership(organization_id={self.organization_id!r}, "
            f"user_id={self.user_id!r}, role={self.role!r})"
        )
