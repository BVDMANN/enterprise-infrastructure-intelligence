"""Organization-scoped RBAC models (P1-A3).

Roles are deliberately organization-scoped in this phase. Platform-wide
roles are deferred until a separate platform-administration boundary exists.
Memberships reference roles through a composite (organization_id, role_id)
foreign key, so a role from tenant A cannot be assigned to tenant B.
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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(Base):
    """A role whose lifetime and scope belong to exactly one organization."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),
        UniqueConstraint("organization_id", "id", name="uq_roles_organization_id_id"),
        CheckConstraint("length(trim(name)) > 0", name="ck_roles_name_nonempty"),
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
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
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

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin",
    )


class Permission(Base):
    """A stable, named API capability."""

    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("name", name="uq_permissions_name"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)

    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        lazy="selectin",
    )


class RolePermission(Base):
    """Many-to-many link between one role and one permission."""

    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
