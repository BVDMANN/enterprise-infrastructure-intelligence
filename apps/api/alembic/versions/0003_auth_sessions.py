"""Create revocable server-side authentication sessions (P1-A2.1).

Only token digests are persisted. OIDC provider configuration and HTTP
cookie endpoints are delivered in separate follow-up work.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003_auth_sessions"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the auth_sessions table and expiry lookup index."""
    op.create_table(
        "auth_sessions",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user_expires",
        "auth_sessions",
        ["user_id", "expires_at"],
    )


def downgrade() -> None:
    """Drop only the session table introduced by this revision."""
    op.drop_index("ix_auth_sessions_user_expires", table_name="auth_sessions")
    op.drop_table("auth_sessions")
