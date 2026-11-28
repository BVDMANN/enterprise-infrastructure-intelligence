"""Record the source of operator and agent metric ingestion (P1-A7.2)."""

from alembic import op
import sqlalchemy as sa

revision = "0012_metric_source"
down_revision = "0011_agent_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add an explicit, constrained ingestion source to metric samples."""
    op.add_column(
        "infrastructure_metrics",
        sa.Column(
            "ingestion_source",
            sa.String(length=24),
            server_default=sa.text("'operator_api'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_infrastructure_metrics_ingestion_source",
        "infrastructure_metrics",
        "ingestion_source IN ('operator_api', 'agent_api')",
    )


def downgrade() -> None:
    """Preserve provenance: refuse to remove the column while agent rows exist."""
    op.execute("ALTER TABLE infrastructure_metrics NO FORCE ROW LEVEL SECURITY")
    bind = op.get_bind()
    agent_sample_count = bind.execute(
        sa.text(
            "SELECT count(*) FROM infrastructure_metrics "
            "WHERE ingestion_source = 'agent_api'"
        )
    ).scalar_one()
    if agent_sample_count:
        raise RuntimeError(
            "Refusing to remove ingestion_source while agent-ingested metrics exist."
        )

    op.execute("ALTER TABLE infrastructure_metrics FORCE ROW LEVEL SECURITY")
    op.drop_constraint(
        "ck_infrastructure_metrics_ingestion_source",
        "infrastructure_metrics",
        type_="check",
    )
    op.drop_column("infrastructure_metrics", "ingestion_source")
