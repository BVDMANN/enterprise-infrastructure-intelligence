"""Add nullable Argon2id password hash to users (P1-A2.2).

Nullable keeps OIDC-only identities valid. Plaintext passwords are never stored.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_user_password_hash"
down_revision = "0003_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add the optional local-auth credential hash."""
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Refuse to discard provisioned credentials during a schema rollback."""
    bind = op.get_bind()
    credential_count = bind.execute(
        sa.text("SELECT count(*) FROM users WHERE password_hash IS NOT NULL")
    ).scalar_one()
    if credential_count:
        raise RuntimeError(
            "Refusing to drop users.password_hash while local credentials exist; "
            "export or explicitly migrate those accounts first."
        )
    op.drop_column("users", "password_hash")
