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
    """Remove citext after all dependent schema revisions are downgraded."""
    op.execute("DROP EXTENSION IF EXISTS citext")
