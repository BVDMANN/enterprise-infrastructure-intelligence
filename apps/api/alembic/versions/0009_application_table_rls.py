"""Enable transaction-local RLS on tenant inventory and audit tables."""

from alembic import op

revision = "0009_application_table_rls"
down_revision = "0008_infrastructure_assets"
branch_labels = None
depends_on = None


_TABLES = ("audit_events", "infrastructure_assets")


def _policy_sql(table: str) -> str:
    """Return a fail-closed policy bound to both tenant and active member."""
    return f"""
        CREATE POLICY eii_{table}_tenant_isolation ON {table}
        FOR ALL TO PUBLIC
        USING (
            {table}.organization_id =
                NULLIF(
                    current_setting('app.current_organization_id', true), ''
                )::uuid
            AND EXISTS (
                SELECT 1
                FROM organizations AS o
                WHERE o.id = {table}.organization_id
                  AND o.deleted_at IS NULL
            )
            AND EXISTS (
                SELECT 1
                FROM memberships AS m
                JOIN users AS u ON u.id = m.user_id
                WHERE m.organization_id = {table}.organization_id
                  AND m.user_id =
                      NULLIF(
                          current_setting('app.current_user_id', true), ''
                      )::uuid
                  AND u.is_active IS TRUE
                  AND u.deleted_at IS NULL
            )
        )
        WITH CHECK (
            {table}.organization_id =
                NULLIF(
                    current_setting('app.current_organization_id', true), ''
                )::uuid
            AND EXISTS (
                SELECT 1
                FROM organizations AS o
                WHERE o.id = {table}.organization_id
                  AND o.deleted_at IS NULL
            )
            AND EXISTS (
                SELECT 1
                FROM memberships AS m
                JOIN users AS u ON u.id = m.user_id
                WHERE m.organization_id = {table}.organization_id
                  AND m.user_id =
                      NULLIF(
                          current_setting('app.current_user_id', true), ''
                      )::uuid
                  AND u.is_active IS TRUE
                  AND u.deleted_at IS NULL
            )
        )
    """


def upgrade() -> None:
    """Require a matching tenant and active member for inventory and audit."""
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(_policy_sql(table))


def downgrade() -> None:
    """Remove the two policies without dropping or changing application data."""
    for table in reversed(_TABLES):
        op.execute(f"DROP POLICY eii_{table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
