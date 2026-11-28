"""Tenant-scoped append-only infrastructure metrics (P1-A6.3)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010_infrastructure_metrics"
down_revision = "0009_application_table_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create metric samples with tenant RLS and append-only guards."""
    op.create_table(
        "infrastructure_metrics",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), nullable=False),
        sa.Column("metric_name", sa.String(length=100), nullable=False),
        sa.Column("metric_value", sa.Numeric(precision=30, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "asset_id"],
            ["infrastructure_assets.organization_id", "infrastructure_assets.id"],
            name="fk_infrastructure_metrics_organization_asset",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(trim(metric_name)) > 0",
            name="ck_infrastructure_metrics_name_nonempty",
        ),
        sa.CheckConstraint(
            "metric_name = lower(metric_name)",
            name="ck_infrastructure_metrics_name_lowercase",
        ),
        sa.CheckConstraint(
            "unit IS NULL OR length(trim(unit)) > 0",
            name="ck_infrastructure_metrics_unit_nonempty",
        ),
    )
    op.create_index(
        "ix_infrastructure_metrics_organization_asset_recorded",
        "infrastructure_metrics",
        ["organization_id", "asset_id", "recorded_at"],
    )
    op.create_index(
        "ix_infrastructure_metrics_organization_name_recorded",
        "infrastructure_metrics",
        ["organization_id", "metric_name", "recorded_at"],
    )

    op.execute("ALTER TABLE infrastructure_metrics ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE infrastructure_metrics FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY eii_infrastructure_metrics_tenant_isolation
        ON infrastructure_metrics
        FOR ALL TO PUBLIC
        USING (
            infrastructure_metrics.organization_id =
                NULLIF(
                    current_setting('app.current_organization_id', true), ''
                )::uuid
            AND EXISTS (
                SELECT 1
                FROM organizations AS o
                WHERE o.id = infrastructure_metrics.organization_id
                  AND o.deleted_at IS NULL
            )
            AND EXISTS (
                SELECT 1
                FROM memberships AS m
                JOIN users AS u ON u.id = m.user_id
                WHERE m.organization_id = infrastructure_metrics.organization_id
                  AND m.user_id =
                      NULLIF(
                          current_setting('app.current_user_id', true), ''
                      )::uuid
                  AND u.is_active IS TRUE
                  AND u.deleted_at IS NULL
            )
        )
        WITH CHECK (
            infrastructure_metrics.organization_id =
                NULLIF(
                    current_setting('app.current_organization_id', true), ''
                )::uuid
            AND EXISTS (
                SELECT 1
                FROM organizations AS o
                WHERE o.id = infrastructure_metrics.organization_id
                  AND o.deleted_at IS NULL
            )
            AND EXISTS (
                SELECT 1
                FROM memberships AS m
                JOIN users AS u ON u.id = m.user_id
                WHERE m.organization_id = infrastructure_metrics.organization_id
                  AND m.user_id =
                      NULLIF(
                          current_setting('app.current_user_id', true), ''
                      )::uuid
                  AND u.is_active IS TRUE
                  AND u.deleted_at IS NULL
            )
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION eii_reject_infrastructure_metric_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'infrastructure_metrics is append-only: % is forbidden', TG_OP
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER infrastructure_metrics_no_update_delete
        BEFORE UPDATE OR DELETE ON infrastructure_metrics
        FOR EACH ROW
        EXECUTE FUNCTION eii_reject_infrastructure_metric_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER infrastructure_metrics_no_truncate
        BEFORE TRUNCATE ON infrastructure_metrics
        FOR EACH STATEMENT
        EXECUTE FUNCTION eii_reject_infrastructure_metric_mutation();
        """
    )


def downgrade() -> None:
    """Refuse to discard collected metric history during a schema rollback."""
    bind = op.get_bind()
    metric_count = bind.execute(
        sa.text("SELECT count(*) FROM infrastructure_metrics")
    ).scalar_one()
    if metric_count:
        raise RuntimeError(
            "Refusing to drop infrastructure_metrics while samples exist."
        )

    op.execute("DROP TRIGGER infrastructure_metrics_no_truncate ON infrastructure_metrics")
    op.execute(
        "DROP TRIGGER infrastructure_metrics_no_update_delete ON infrastructure_metrics"
    )
    op.execute("DROP FUNCTION eii_reject_infrastructure_metric_mutation()")
    op.execute(
        "DROP POLICY eii_infrastructure_metrics_tenant_isolation "
        "ON infrastructure_metrics"
    )
    op.execute("ALTER TABLE infrastructure_metrics NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE infrastructure_metrics DISABLE ROW LEVEL SECURITY")
    op.drop_index(
        "ix_infrastructure_metrics_organization_name_recorded",
        table_name="infrastructure_metrics",
    )
    op.drop_index(
        "ix_infrastructure_metrics_organization_asset_recorded",
        table_name="infrastructure_metrics",
    )
    op.drop_table("infrastructure_metrics")
