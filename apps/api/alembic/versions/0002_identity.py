"""Identity tables — organizations, users, memberships (P1-A1).

Depends on 0001_pg_extensions for CITEXT (case-insensitive email).
No public route is opened by this lot; the tables are the tenant
foundation for P1-A2 (OIDC/sessions) and P1-A3 (RBAC).

Notes:
- IDs are generated in Python (uuid.uuid4); no database-side default,
  so the schema stays testable on SQLite (see app/models/identity.py).
- ``memberships.role`` is a string guarded by a CHECK constraint until
  RBAC (P1-A3) replaces it with a ``role_id`` foreign key.
- Foreign keys use ON DELETE RESTRICT: an organization or user with
  memberships cannot be hard-deleted.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, UUID

# Same email type as the model: CITEXT on PostgreSQL, plain String
# elsewhere. postgresql.CITEXT alone has no SQLite compiler, so the
# Variant keeps the migration renderable on every backend.
EMAIL_TYPE = sa.String().with_variant(CITEXT(), "postgresql")

revision = "0002_identity"
down_revision = "0001_pg_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create organizations, users and memberships."""
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", EMAIL_TYPE, nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("oidc_subject", sa.String(length=255), nullable=True),
        sa.Column(
            "mfa_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("oidc_subject", name="uq_users_oidc_subject"),
    )
    op.create_table(
        "memberships",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "role",
            sa.String(length=32),
            server_default="member",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_memberships_organization_user",
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'viewer')",
            name="ck_memberships_role",
        ),
    )
    op.create_index(
        "ix_memberships_organization_id", "memberships", ["organization_id"]
    )
    op.create_index("ix_memberships_user_id", "memberships", ["user_id"])


def downgrade() -> None:
    """Drop memberships, users and organizations (reverse order)."""
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_index("ix_memberships_organization_id", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("users")
    op.drop_table("organizations")
