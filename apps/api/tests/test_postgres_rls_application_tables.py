"""RLS integration against real application tables and the runtime role.

The CI PostgreSQL service is ephemeral. This test seeds uniquely identified
rows and leaves them in that disposable database; it never targets a shared
or production database.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.skipif(
    os.getenv("EII_POSTGRES_RLS_APPLICATION") != "1",
    reason="Requires the least-privilege application PostgreSQL integration job.",
)


def _set_context(connection, organization_id, user_id) -> None:
    connection.execute(
        text(
            "SELECT set_config("
            "'app.current_organization_id', :organization_id, true)"
        ),
        {"organization_id": str(organization_id)},
    )
    connection.execute(
        text("SELECT set_config('app.current_user_id', :user_id, true)"),
        {"user_id": str(user_id)},
    )


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(
        error.orig, "pgcode", None
    )


def test_real_inventory_and_audit_tables_enforce_tenant_rls() -> None:
    """Verify fail-closed reads/writes with the actual eii_runtime login."""
    runtime_url = os.environ.get("DATABASE_URL")
    migration_url = os.environ.get("MIGRATION_DATABASE_URL")
    assert runtime_url, "DATABASE_URL must use the non-superuser runtime role."
    assert migration_url, "MIGRATION_DATABASE_URL must use the migrator role."

    runtime_role = os.getenv("EII_RUNTIME_ROLE", "eii_runtime")
    migrator_role = os.getenv("EII_MIGRATOR_ROLE", "eii_migrator")
    runtime_engine = create_engine(
        runtime_url, pool_size=1, max_overflow=0, pool_pre_ping=True
    )
    migrator_engine = create_engine(migration_url, pool_pre_ping=True)

    suffix = uuid4().hex
    organization_a = uuid4()
    organization_b = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    role_a = uuid4()
    role_b = uuid4()
    membership_a = uuid4()
    membership_b = uuid4()
    asset_a = uuid4()
    asset_b = uuid4()
    event_a = uuid4()
    event_b = uuid4()

    try:
        # The migration owner is subject to FORCE RLS too; seed each tenant
        # only after setting both transaction-local context values.
        with migrator_engine.begin() as connection:
            assert connection.scalar(text("SELECT current_user")) == migrator_role

            role_flags = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = :role"
                ),
                {"role": runtime_role},
            ).one()
            assert role_flags.rolsuper is False
            assert role_flags.rolbypassrls is False

            table_flags = connection.execute(
                text(
                    """
                    SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                           pg_get_userbyid(c.relowner)
                    FROM pg_class AS c
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relname IN ('audit_events', 'infrastructure_assets')
                    ORDER BY c.relname
                    """
                )
            ).all()
            assert len(table_flags) == 2
            for name, enabled, forced, owner in table_flags:
                assert enabled is True, name
                assert forced is True, name
                assert owner == migrator_role, name

            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, :name, :slug)"
                ),
                [
                    {
                        "id": organization_a,
                        "name": f"RLS A {suffix}",
                        "slug": f"rls-a-{suffix}",
                    },
                    {
                        "id": organization_b,
                        "name": f"RLS B {suffix}",
                        "slug": f"rls-b-{suffix}",
                    },
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name, is_active) "
                    "VALUES (:id, :email, :display_name, true)"
                ),
                [
                    {
                        "id": user_a,
                        "email": f"rls-a-{suffix}@example.test",
                        "display_name": "RLS User A",
                    },
                    {
                        "id": user_b,
                        "email": f"rls-b-{suffix}@example.test",
                        "display_name": "RLS User B",
                    },
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO roles "
                    "(id, organization_id, name, description, is_system) "
                    "VALUES (:id, :organization_id, 'owner', 'RLS test owner', true)"
                ),
                [
                    {"id": role_a, "organization_id": organization_a},
                    {"id": role_b, "organization_id": organization_b},
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO memberships (id, organization_id, user_id, role_id) "
                    "VALUES (:id, :organization_id, :user_id, :role_id)"
                ),
                [
                    {
                        "id": membership_a,
                        "organization_id": organization_a,
                        "user_id": user_a,
                        "role_id": role_a,
                    },
                    {
                        "id": membership_b,
                        "organization_id": organization_b,
                        "user_id": user_b,
                        "role_id": role_b,
                    },
                ],
            )

            _set_context(connection, organization_a, user_a)
            connection.execute(
                text(
                    "INSERT INTO infrastructure_assets "
                    "(id, organization_id, name, asset_type) "
                    "VALUES (:id, :organization_id, 'RLS asset A', 'server')"
                ),
                {"id": asset_a, "organization_id": organization_a},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(id, organization_id, actor_user_id, event_type) "
                    "VALUES (:id, :organization_id, :actor_user_id, 'rls.test.a')"
                ),
                {
                    "id": event_a,
                    "organization_id": organization_a,
                    "actor_user_id": user_a,
                },
            )

            _set_context(connection, organization_b, user_b)
            connection.execute(
                text(
                    "INSERT INTO infrastructure_assets "
                    "(id, organization_id, name, asset_type) "
                    "VALUES (:id, :organization_id, 'RLS asset B', 'server')"
                ),
                {"id": asset_b, "organization_id": organization_b},
            )
            connection.execute(
                text(
                    "INSERT INTO audit_events "
                    "(id, organization_id, actor_user_id, event_type) "
                    "VALUES (:id, :organization_id, :actor_user_id, 'rls.test.b')"
                ),
                {
                    "id": event_b,
                    "organization_id": organization_b,
                    "actor_user_id": user_b,
                },
            )

        with runtime_engine.connect() as connection:
            # Missing context is default-deny for reads and writes.
            with connection.begin():
                assert connection.scalar(text("SELECT current_user")) == runtime_role
                assert connection.scalar(
                    text("SELECT count(*) FROM infrastructure_assets")
                ) == 0
                assert connection.scalar(
                    text("SELECT count(*) FROM audit_events")
                ) == 0
                with pytest.raises(DBAPIError) as denied_without_context:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "INSERT INTO infrastructure_assets "
                                "(id, organization_id, name, asset_type) "
                                "VALUES (:id, :organization_id, 'No context', 'server')"
                            ),
                            {"id": uuid4(), "organization_id": organization_a},
                        )
                assert _sqlstate(denied_without_context.value) == "42501"

            # User A sees only A. Cross-tenant writes are rejected even when
            # the target row exists and user B is a valid member of B.
            with connection.begin():
                _set_context(connection, organization_a, user_a)
                assert connection.scalars(
                    text(
                        "SELECT id FROM infrastructure_assets ORDER BY id"
                    )
                ).all() == [asset_a]
                assert connection.scalars(
                    text("SELECT id FROM audit_events ORDER BY id")
                ).all() == [event_a]

                with pytest.raises(DBAPIError) as denied_cross_insert:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "INSERT INTO infrastructure_assets "
                                "(id, organization_id, name, asset_type) "
                                "VALUES (:id, :organization_id, 'Cross tenant', "
                                "'server')"
                            ),
                            {"id": uuid4(), "organization_id": organization_b},
                        )
                assert _sqlstate(denied_cross_insert.value) == "42501"

                with pytest.raises(DBAPIError) as denied_cross_update:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "UPDATE infrastructure_assets "
                                "SET organization_id = :organization_b "
                                "WHERE id = :asset_a"
                            ),
                            {
                                "organization_b": organization_b,
                                "asset_a": asset_a,
                            },
                        )
                assert _sqlstate(denied_cross_update.value) == "42501"

                hidden_asset_delete = connection.execute(
                    text("DELETE FROM infrastructure_assets WHERE id = :asset_b"),
                    {"asset_b": asset_b},
                )
                assert hidden_asset_delete.rowcount == 0

                with pytest.raises(DBAPIError) as denied_audit_insert:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "INSERT INTO audit_events "
                                "(id, organization_id, actor_user_id, event_type) "
                                "VALUES (:id, :organization_id, :actor_user_id, "
                                "'cross.tenant')"
                            ),
                            {
                                "id": uuid4(),
                                "organization_id": organization_b,
                                "actor_user_id": user_b,
                            },
                        )
                assert _sqlstate(denied_audit_insert.value) == "42501"

                hidden_audit_delete = connection.execute(
                    text("DELETE FROM audit_events WHERE id = :event_b"),
                    {"event_b": event_b},
                )
                assert hidden_audit_delete.rowcount == 0

                # A valid tenant ID alone is insufficient: the context user
                # must also have an active membership in that tenant.
                _set_context(connection, organization_b, user_a)
                assert connection.scalar(
                    text("SELECT count(*) FROM infrastructure_assets")
                ) == 0
                assert connection.scalar(
                    text("SELECT count(*) FROM audit_events")
                ) == 0

                _set_context(connection, organization_b, user_b)
                assert connection.scalars(
                    text("SELECT id FROM infrastructure_assets")
                ).all() == [asset_b]
                assert connection.scalars(
                    text("SELECT id FROM audit_events")
                ).all() == [event_b]

            # SET LOCAL / set_config(..., true) must not leak through a
            # pooled runtime connection into the next request transaction.
            with connection.begin():
                assert connection.scalar(
                    text("SELECT count(*) FROM infrastructure_assets")
                ) == 0
                assert connection.scalar(
                    text("SELECT count(*) FROM audit_events")
                ) == 0
    finally:
        runtime_engine.dispose()
        migrator_engine.dispose()
