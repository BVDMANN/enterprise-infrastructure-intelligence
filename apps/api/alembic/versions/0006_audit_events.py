"""Tenant-scoped append-only audit events (P1-A5)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0006_audit_events"
down_revision = "0005_rbac_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tenant-attributed events and PostgreSQL mutation guards."""
    op.create_table(
        "audit_events",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column(
            "details",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_audit_events_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_events_actor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_audit_events_organization_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(trim(event_type)) > 0",
            name="ck_audit_events_event_type_nonempty",
        ),
        sa.CheckConstraint(
            "target_type IS NULL OR length(trim(target_type)) > 0",
            name="ck_audit_events_target_type_nonempty",
        ),
        sa.CheckConstraint(
            "request_id IS NULL OR length(trim(request_id)) > 0",
            name="ck_audit_events_request_id_nonempty",
        ),
    )
    op.create_index(
        "ix_audit_events_organization_occurred_at",
        "audit_events",
        ["organization_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_organization_actor_occurred_at",
        "audit_events",
        ["organization_id", "actor_user_id", "occurred_at"],
    )

    op.execute(
        """
        CREATE FUNCTION eii_reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events is append-only: % is forbidden', TG_OP
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION eii_reject_audit_event_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_truncate
        BEFORE TRUNCATE ON audit_events
        FOR EACH STATEMENT
        EXECUTE FUNCTION eii_reject_audit_event_mutation();
        """
    )


def downgrade() -> None:
    """Refuse to discard audit history during a schema rollback."""
    bind = op.get_bind()
    event_count = bind.execute(
        sa.text("SELECT count(*) FROM audit_events")
    ).scalar_one()
    if event_count:
        raise RuntimeError(
            "Refusing to drop audit_events while audit history exists."
        )

    op.execute("DROP TRIGGER audit_events_no_truncate ON audit_events")
    op.execute("DROP TRIGGER audit_events_no_update_delete ON audit_events")
    op.execute("DROP FUNCTION eii_reject_audit_event_mutation()")
    op.drop_index(
        "ix_audit_events_organization_actor_occurred_at",
        table_name="audit_events",
    )
    op.drop_index(
        "ix_audit_events_organization_occurred_at",
        table_name="audit_events",
    )
    op.drop_table("audit_events")
