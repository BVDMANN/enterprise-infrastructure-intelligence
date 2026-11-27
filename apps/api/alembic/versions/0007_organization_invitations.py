"""Member invitations by manual link (P1-A1 completion).

Depends on 0006_audit_events. Creates the ``invitations`` table: an
invitation binds one email to one organization-scoped role, with a
single-use opaque token (only its SHA-256 digest is persisted), an
expiry, and revocation/acceptance timestamps.

No transactional email is sent in PHASE 1 (PHASE1_PLAN.md D5): the
token is returned once at creation and the inviter copies the accept
link manually. The token is never written to the audit log.

Notes:
- ``email`` uses CITEXT on PostgreSQL (case-insensitive), plain String
  elsewhere — the same Variant as migration 0002.
- The composite foreign key (organization_id, role_id) guarantees the
  invited role belongs to the invited organization, exactly like
  ``memberships`` (migration 0005).
- Foreign keys use ON DELETE RESTRICT: an organization, user or role
  with invitations cannot be hard-deleted.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT, UUID

# Same email type as the model: CITEXT on PostgreSQL, plain String
# elsewhere. postgresql.CITEXT alone has no SQLite compiler, so the
# Variant keeps the migration renderable on every backend.
EMAIL_TYPE = sa.String().with_variant(CITEXT(), "postgresql")

revision = "0007_organization_invitations"
down_revision = "0006_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the invitations table."""
    op.create_table(
        "invitations",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", EMAIL_TYPE, nullable=False),
        sa.Column("role_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("accepted_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("invited_by_user_id", UUID(as_uuid=True), nullable=False),
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
            name="fk_invitations_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_user_id"],
            ["users.id"],
            name="fk_invitations_accepted_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            name="fk_invitations_invited_by_user",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "role_id"],
            ["roles.organization_id", "roles.id"],
            name="fk_invitations_organization_role",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index(
        "ix_invitations_organization_email",
        "invitations",
        ["organization_id", "email"],
    )


def downgrade() -> None:
    """Drop the invitations table."""
    op.drop_index("ix_invitations_organization_email", table_name="invitations")
    op.drop_table("invitations")
