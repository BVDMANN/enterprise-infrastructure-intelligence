"""Tenant-scoped infrastructure asset inventory (P1-A6.1)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008_infrastructure_assets"
down_revision = "0007_organization_invitations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create organization-owned inventory records and lookup indexes."""
    op.create_table(
        "infrastructure_assets",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_type", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=128), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column(
            "attributes",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_infrastructure_assets_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "external_id",
            name="uq_infrastructure_assets_organization_external_id",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            name="uq_infrastructure_assets_organization_id_id",
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_infrastructure_assets_name_nonempty",
        ),
        sa.CheckConstraint(
            "asset_type IN ('server', 'virtual_machine', 'container', 'cluster', "
            "'database', 'network', 'storage', 'cloud_resource', 'service', 'other')",
            name="ck_infrastructure_assets_type",
        ),
        sa.CheckConstraint(
            "status IN ('unknown', 'healthy', 'degraded', 'unhealthy', 'offline')",
            name="ck_infrastructure_assets_status",
        ),
        sa.CheckConstraint(
            "external_id IS NULL OR length(trim(external_id)) > 0",
            name="ck_infrastructure_assets_external_id_nonempty",
        ),
        sa.CheckConstraint(
            "provider IS NULL OR length(trim(provider)) > 0",
            name="ck_infrastructure_assets_provider_nonempty",
        ),
        sa.CheckConstraint(
            "region IS NULL OR length(trim(region)) > 0",
            name="ck_infrastructure_assets_region_nonempty",
        ),
    )
    op.create_index(
        "ix_infrastructure_assets_organization_status",
        "infrastructure_assets",
        ["organization_id", "status"],
    )
    op.create_index(
        "ix_infrastructure_assets_organization_type",
        "infrastructure_assets",
        ["organization_id", "asset_type"],
    )
    op.create_index(
        "ix_infrastructure_assets_organization_updated_at",
        "infrastructure_assets",
        ["organization_id", "updated_at"],
    )


def downgrade() -> None:
    """Refuse to discard an inventory while records still exist."""
    bind = op.get_bind()
    asset_count = bind.execute(
        sa.text("SELECT count(*) FROM infrastructure_assets")
    ).scalar_one()
    if asset_count:
        raise RuntimeError(
            "Refusing to drop infrastructure_assets while inventory records exist."
        )

    op.drop_index(
        "ix_infrastructure_assets_organization_updated_at",
        table_name="infrastructure_assets",
    )
    op.drop_index(
        "ix_infrastructure_assets_organization_type",
        table_name="infrastructure_assets",
    )
    op.drop_index(
        "ix_infrastructure_assets_organization_status",
        table_name="infrastructure_assets",
    )
    op.drop_table("infrastructure_assets")
