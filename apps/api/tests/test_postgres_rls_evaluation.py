"""Isolated PostgreSQL Row-Level Security evaluation prototype.

This test does not modify the application's Alembic schema. It creates a
temporary schema and two temporary non-login roles in the dedicated CI
database, then removes them. It evaluates PostgreSQL mechanics only; it is
not evidence that production application traffic is protected by RLS.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.skipif(
    os.getenv("EII_POSTGRES_RLS_EVALUATION") != "1",
    reason="Requires the isolated PostgreSQL RLS evaluation CI job.",
)


def test_rls_is_fail_closed_tenant_scoped_and_transaction_local() -> None:
    """Verify RLS policies with non-owner, non-superuser database roles."""
    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must target the ephemeral PostgreSQL service."

    engine = create_engine(
        database_url,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
    suffix = uuid4().hex
    schema = f"eii_rls_{suffix}"
    owner_role = f"eii_rls_owner_{suffix}"
    runtime_role = f"eii_rls_runtime_{suffix}"
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    table = f'"{schema}".tenant_records'

    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.exec_driver_sql(
                    f'CREATE ROLE "{owner_role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'
                )
                connection.exec_driver_sql(
                    f'CREATE ROLE "{runtime_role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'
                )
                connection.exec_driver_sql(
                    f'CREATE SCHEMA "{schema}" AUTHORIZATION "{owner_role}"'
                )
                connection.exec_driver_sql(f'SET LOCAL ROLE "{owner_role}"')
                connection.exec_driver_sql(
                    f"CREATE TABLE {table} ("
                    "organization_id uuid NOT NULL, payload text NOT NULL)"
                )
                connection.execute(
                    text(
                        f"INSERT INTO {table} (organization_id, payload) "
                        "VALUES (:tenant_id, :payload)"
                    ),
                    [
                        {"tenant_id": tenant_a, "payload": "tenant-a"},
                        {"tenant_id": tenant_b, "payload": "tenant-b"},
                    ],
                )
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
                )
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"
                )
                connection.exec_driver_sql(
                    f"""
                    CREATE POLICY tenant_isolation ON {table}
                    USING (
                        organization_id =
                        NULLIF(
                            current_setting('app.current_organization_id', true),
                            ''
                        )::uuid
                    )
                    WITH CHECK (
                        organization_id =
                        NULLIF(
                            current_setting('app.current_organization_id', true),
                            ''
                        )::uuid
                    )
                    """
                )
                connection.exec_driver_sql("RESET ROLE")
                connection.exec_driver_sql(
                    f'GRANT USAGE ON SCHEMA "{schema}" TO "{runtime_role}"'
                )
                connection.exec_driver_sql(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} "
                    f'TO "{runtime_role}"'
                )

                for role in (owner_role, runtime_role):
                    attributes = connection.execute(
                        text(
                            "SELECT rolsuper, rolbypassrls FROM pg_roles "
                            "WHERE rolname = :role"
                        ),
                        {"role": role},
                    ).one()
                    assert attributes[0] is False
                    assert attributes[1] is False

                table_owner = connection.scalar(
                    text(
                        "SELECT tableowner FROM pg_tables "
                        "WHERE schemaname = :schema AND tablename = 'tenant_records'"
                    ),
                    {"schema": schema},
                )
                assert table_owner == owner_role

            # FORCE ROW LEVEL SECURITY also subjects the non-superuser owner.
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{owner_role}"')
                assert connection.scalar(text("SELECT current_user")) == owner_role
                assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
                connection.execute(
                    text(
                        "SELECT set_config("
                        "'app.current_organization_id', :tenant_id, true)"
                    ),
                    {"tenant_id": tenant_a},
                )
                owner_rows = connection.scalars(
                    text(f"SELECT payload FROM {table} ORDER BY payload")
                ).all()
                assert owner_rows == ["tenant-a"]

            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                assert connection.scalar(text("SELECT current_user")) == runtime_role
                assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0

                connection.execute(
                    text(
                        "SELECT set_config("
                        "'app.current_organization_id', :tenant_id, true)"
                    ),
                    {"tenant_id": tenant_a},
                )
                tenant_a_rows = connection.scalars(
                    text(f"SELECT payload FROM {table} ORDER BY payload")
                ).all()
                assert tenant_a_rows == ["tenant-a"]

                with pytest.raises(DBAPIError) as denied_insert:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                f"INSERT INTO {table} (organization_id, payload) "
                                "VALUES (:tenant_id, 'cross-tenant-insert')"
                            ),
                            {"tenant_id": tenant_b},
                        )
                insert_sqlstate = getattr(
                    denied_insert.value.orig, "sqlstate", None
                ) or getattr(denied_insert.value.orig, "pgcode", None)
                assert insert_sqlstate == "42501"

                with pytest.raises(DBAPIError) as denied_update:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                f"UPDATE {table} SET organization_id = :tenant_id "
                                "WHERE payload = 'tenant-a'"
                            ),
                            {"tenant_id": tenant_b},
                        )
                update_sqlstate = getattr(
                    denied_update.value.orig, "sqlstate", None
                ) or getattr(denied_update.value.orig, "pgcode", None)
                assert update_sqlstate == "42501"

                hidden_delete = connection.execute(
                    text(f"DELETE FROM {table} WHERE payload = 'tenant-b'")
                )
                assert hidden_delete.rowcount == 0

                connection.execute(
                    text(
                        f"INSERT INTO {table} (organization_id, payload) "
                        "VALUES (:tenant_id, 'tenant-a-inserted')"
                    ),
                    {"tenant_id": tenant_a},
                )

                connection.execute(
                    text(
                        "SELECT set_config("
                        "'app.current_organization_id', :tenant_id, true)"
                    ),
                    {"tenant_id": tenant_b},
                )
                tenant_b_rows = connection.scalars(
                    text(f"SELECT payload FROM {table} ORDER BY payload")
                ).all()
                assert tenant_b_rows == ["tenant-b"]
                connection.execute(
                    text(
                        f"INSERT INTO {table} (organization_id, payload) "
                        "VALUES (:tenant_id, 'tenant-b-inserted')"
                    ),
                    {"tenant_id": tenant_b},
                )

            # Reuse the same pooled connection: SET LOCAL and the tenant GUC
            # must not leak into the next transaction.
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                context = connection.scalar(
                    text(
                        "SELECT NULLIF("
                        "current_setting('app.current_organization_id', true), '')"
                    )
                )
                assert context is None
                assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    finally:
        try:
            with engine.begin() as cleanup:
                cleanup.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                cleanup.exec_driver_sql(f'DROP ROLE IF EXISTS "{runtime_role}"')
                cleanup.exec_driver_sql(f'DROP ROLE IF EXISTS "{owner_role}"')
        finally:
            engine.dispose()
