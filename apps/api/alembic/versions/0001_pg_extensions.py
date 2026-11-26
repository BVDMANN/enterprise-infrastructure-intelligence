"""Install PostgreSQL extensions required by the Phase 1 schema.

The first identity models use CITEXT for case-insensitive email uniqueness.
No application tables or data are modified by this migration.
"""

from alembic import op

revision = "0001_pg_extensions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Install citext for case-insensitive identity fields."""
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")


def downgrade() -> None:
    """Retain the shared extension; removing it could break another schema."""
    # CREATE EXTENSION IF NOT EXISTS is safe to replay. citext is deliberately
    # retained on downgrade because extensions may be shared at database level.
    pass
