"""Asset-scoped, revocable infrastructure agent credentials (P1-A7.1)."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011_infrastructure_agent_credentials"
down_revision = "0010_infrastructure_metrics"
branch_labels = None
depends_on = None


def _member_policy(table: str) -> str:
    """Require the selected organization and an active enrolling member."""
    return f"""
        {table}.organization_id =
            NULLIF(current_setting('app.current_organization_id', true), '')::uuid
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
                  NULLIF(current_setting('app.current_user_id', true), '')::uuid
              AND u.is_active IS TRUE
              AND u.deleted_at IS NULL
        )
    """


def upgrade() -> None:
    """Create hashed credentials with member management and token lookup RLS."""
    op.create_table(
        "infrastructure_agent_credentials",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_prefix", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id", "asset_id"],
            ["infrastructure_assets.organization_id", "infrastructure_assets.id"],
            name="fk_agent_credentials_organization_asset",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_agent_credentials_created_by_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_agent_credentials_token_hash",
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_agent_credentials_name_nonempty",
        ),
        sa.CheckConstraint(
            "length(token_hash) = 64",
            name="ck_agent_credentials_token_hash_length",
        ),
        sa.CheckConstraint(
            "length(token_prefix) BETWEEN 1 AND 24",
            name="ck_agent_credentials_token_prefix_length",
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_agent_credentials_expiry_after_creation",
        ),
    )
    op.create_index(
        "ix_agent_credentials_organization_asset_created",
        "infrastructure_agent_credentials",
        ["organization_id", "asset_id", "created_at"],
    )

    op.execute(
        "ALTER TABLE infrastructure_agent_credentials ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE infrastructure_agent_credentials FORCE ROW LEVEL SECURITY"
    )
    member = _member_policy("infrastructure_agent_credentials")
    op.execute(
        f"""
        CREATE POLICY eii_agent_credentials_member_select
        ON infrastructure_agent_credentials
        FOR SELECT TO PUBLIC
        USING ({member})
        """
    )
    op.execute(
        """
        CREATE POLICY eii_agent_credentials_token_lookup
        ON infrastructure_agent_credentials
        FOR SELECT TO PUBLIC
        USING (
            token_hash =
                NULLIF(current_setting('app.current_agent_token_hash', true), '')
            AND revoked_at IS NULL
            AND expires_at > now()
        )
        """
    )
    op.execute(
        f"""
        CREATE POLICY eii_agent_credentials_member_insert
        ON infrastructure_agent_credentials
        FOR INSERT TO PUBLIC
        WITH CHECK ({member})
        """
    )
    op.execute(
        f"""
        CREATE POLICY eii_agent_credentials_member_update
        ON infrastructure_agent_credentials
        FOR UPDATE TO PUBLIC
        USING ({member})
        WITH CHECK ({member})
        """
    )

    op.execute(
        """
        CREATE FUNCTION eii_guard_agent_credential_update()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.id IS DISTINCT FROM OLD.id
                OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
                OR NEW.asset_id IS DISTINCT FROM OLD.asset_id
                OR NEW.created_by_user_id IS DISTINCT FROM OLD.created_by_user_id
                OR NEW.name IS DISTINCT FROM OLD.name
                OR NEW.token_hash IS DISTINCT FROM OLD.token_hash
                OR NEW.token_prefix IS DISTINCT FROM OLD.token_prefix
                OR NEW.created_at IS DISTINCT FROM OLD.created_at
                OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
            THEN
                RAISE EXCEPTION
                    'agent credential identity fields are immutable'
                    USING ERRCODE = '55000';
            END IF;

            IF OLD.revoked_at IS NOT NULL
                AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at
            THEN
                RAISE EXCEPTION
                    'agent credential revocation is irreversible'
                    USING ERRCODE = '55000';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER agent_credentials_immutable_identity
        BEFORE UPDATE ON infrastructure_agent_credentials
        FOR EACH ROW
        EXECUTE FUNCTION eii_guard_agent_credential_update();
        """
    )
    op.execute(
        """
        CREATE FUNCTION eii_reject_agent_credential_truncate()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'infrastructure_agent_credentials cannot be truncated'
                USING ERRCODE = '55000';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER agent_credentials_no_truncate
        BEFORE TRUNCATE ON infrastructure_agent_credentials
        FOR EACH STATEMENT
        EXECUTE FUNCTION eii_reject_agent_credential_truncate();
        """
    )


def downgrade() -> None:
    """Refuse to discard credential history during a schema rollback."""
    # FORCE RLS also filters the table owner. Temporarily remove FORCE inside
    # this migration transaction so the safety count sees every tenant row.
    # If records exist, the raised exception rolls this DDL back as well.
    op.execute(
        "ALTER TABLE infrastructure_agent_credentials NO FORCE ROW LEVEL SECURITY"
    )
    bind = op.get_bind()
    credential_count = bind.execute(
        sa.text("SELECT count(*) FROM infrastructure_agent_credentials")
    ).scalar_one()
    if credential_count:
        raise RuntimeError(
            "Refusing to drop infrastructure_agent_credentials while credentials exist."
        )

    op.execute(
        "DROP TRIGGER agent_credentials_no_truncate "
        "ON infrastructure_agent_credentials"
    )
    op.execute(
        "DROP TRIGGER agent_credentials_immutable_identity "
        "ON infrastructure_agent_credentials"
    )
    op.execute("DROP FUNCTION eii_reject_agent_credential_truncate()")
    op.execute("DROP FUNCTION eii_guard_agent_credential_update()")
    for policy in (
        "eii_agent_credentials_member_update",
        "eii_agent_credentials_member_insert",
        "eii_agent_credentials_token_lookup",
        "eii_agent_credentials_member_select",
    ):
        op.execute(
            f"DROP POLICY {policy} ON infrastructure_agent_credentials"
        )
    op.execute(
        "ALTER TABLE infrastructure_agent_credentials NO FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE infrastructure_agent_credentials DISABLE ROW LEVEL SECURITY"
    )
    op.drop_index(
        "ix_agent_credentials_organization_asset_created",
        table_name="infrastructure_agent_credentials",
    )
    op.drop_table("infrastructure_agent_credentials")
