"""PostgreSQL RLS and append-only checks for infrastructure metric samples."""

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
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


def _assert_metric_insert_denied(connection, organization_id, asset_id) -> None:
    """Verify a revoked tenant identity cannot append another metric sample."""
    with pytest.raises(DBAPIError) as denied_insert:
        with connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO infrastructure_metrics "
                    "(id, organization_id, asset_id, metric_name, metric_value) "
                    "VALUES (:id, :organization_id, :asset_id, "
                    "'cpu.utilization', 99)"
                ),
                {
                    "id": uuid4(),
                    "organization_id": organization_id,
                    "asset_id": asset_id,
                },
            )
    assert _sqlstate(denied_insert.value) == "42501"


def test_infrastructure_metrics_enforce_tenant_rls_and_append_only() -> None:
    """Verify the real runtime role cannot cross tenants or mutate samples."""
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
    metric_a = uuid4()
    metric_b = uuid4()

    try:
        with migrator_engine.begin() as connection:
            assert connection.scalar(text("SELECT current_user")) == migrator_role
            runtime_flags = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = :role"
                ),
                {"role": runtime_role},
            ).one()
            assert runtime_flags.rolsuper is False
            assert runtime_flags.rolbypassrls is False

            table_flags = connection.execute(
                text(
                    """
                    SELECT c.relrowsecurity, c.relforcerowsecurity,
                           pg_get_userbyid(c.relowner) AS owner
                    FROM pg_class AS c
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relname = 'infrastructure_metrics'
                    """
                )
            ).one()
            assert table_flags.relrowsecurity is True
            assert table_flags.relforcerowsecurity is True
            assert table_flags.owner == migrator_role

            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, :name, :slug)"
                ),
                [
                    {
                        "id": organization_a,
                        "name": f"Metrics A {suffix}",
                        "slug": f"metrics-a-{suffix}",
                    },
                    {
                        "id": organization_b,
                        "name": f"Metrics B {suffix}",
                        "slug": f"metrics-b-{suffix}",
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
                        "email": f"metrics-a-{suffix}@example.test",
                        "display_name": "Metrics User A",
                    },
                    {
                        "id": user_b,
                        "email": f"metrics-b-{suffix}@example.test",
                        "display_name": "Metrics User B",
                    },
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO roles "
                    "(id, organization_id, name, description, is_system) "
                    "VALUES (:id, :organization_id, 'owner', 'Metrics test owner', true)"
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
                    "VALUES (:id, :organization_id, 'Metrics asset A', 'server')"
                ),
                {"id": asset_a, "organization_id": organization_a},
            )
            connection.execute(
                text(
                    "INSERT INTO infrastructure_metrics "
                    "(id, organization_id, asset_id, metric_name, metric_value, unit) "
                    "VALUES (:id, :organization_id, :asset_id, "
                    "'cpu.utilization', 42.5, '%')"
                ),
                {
                    "id": metric_a,
                    "organization_id": organization_a,
                    "asset_id": asset_a,
                },
            )

            _set_context(connection, organization_b, user_b)
            connection.execute(
                text(
                    "INSERT INTO infrastructure_assets "
                    "(id, organization_id, name, asset_type) "
                    "VALUES (:id, :organization_id, 'Metrics asset B', 'server')"
                ),
                {"id": asset_b, "organization_id": organization_b},
            )
            connection.execute(
                text(
                    "INSERT INTO infrastructure_metrics "
                    "(id, organization_id, asset_id, metric_name, metric_value, unit) "
                    "VALUES (:id, :organization_id, :asset_id, "
                    "'cpu.utilization', 80, '%')"
                ),
                {
                    "id": metric_b,
                    "organization_id": organization_b,
                    "asset_id": asset_b,
                },
            )

        with runtime_engine.connect() as connection:
            with connection.begin():
                assert connection.scalar(text("SELECT current_user")) == runtime_role
                assert (
                    connection.scalar(
                        text("SELECT count(*) FROM infrastructure_metrics")
                    )
                    == 0
                )

            with connection.begin():
                _set_context(connection, organization_a, user_a)
                assert connection.scalars(
                    text("SELECT id FROM infrastructure_metrics")
                ).all() == [metric_a]

                with pytest.raises(DBAPIError) as denied_cross_insert:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "INSERT INTO infrastructure_metrics "
                                "(id, organization_id, asset_id, metric_name, metric_value) "
                                "VALUES (:id, :organization_id, :asset_id, "
                                "'cpu.utilization', 99)"
                            ),
                            {
                                "id": uuid4(),
                                "organization_id": organization_b,
                                "asset_id": asset_b,
                            },
                        )
                assert _sqlstate(denied_cross_insert.value) == "42501"

                with pytest.raises(DBAPIError) as denied_update:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "UPDATE infrastructure_metrics SET metric_value = 99 "
                                "WHERE id = :metric_id"
                            ),
                            {"metric_id": metric_a},
                        )
                assert _sqlstate(denied_update.value) == "55000"

                with pytest.raises(DBAPIError) as denied_delete:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "DELETE FROM infrastructure_metrics "
                                "WHERE id = :metric_id"
                            ),
                            {"metric_id": metric_a},
                        )
                assert _sqlstate(denied_delete.value) == "55000"

                with pytest.raises(DBAPIError) as denied_runtime_truncate:
                    with connection.begin_nested():
                        connection.execute(
                            text("TRUNCATE TABLE infrastructure_metrics")
                        )
                assert _sqlstate(denied_runtime_truncate.value) == "42501"
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM infrastructure_metrics "
                            "WHERE id = :metric_id"
                        ),
                        {"metric_id": metric_a},
                    )
                    == 1
                )

            with connection.begin():
                _set_context(connection, organization_b, user_a)
                assert (
                    connection.scalar(
                        text("SELECT count(*) FROM infrastructure_metrics")
                    )
                    == 0
                )
                _set_context(connection, organization_b, user_b)
                assert connection.scalars(
                    text("SELECT id FROM infrastructure_metrics")
                ).all() == [metric_b]

        with migrator_engine.connect() as owner_connection:
            with owner_connection.begin():
                _set_context(owner_connection, organization_a, user_a)
                with pytest.raises(DBAPIError) as denied_owner_truncate:
                    with owner_connection.begin_nested():
                        owner_connection.execute(
                            text("TRUNCATE TABLE infrastructure_metrics")
                        )
                assert _sqlstate(denied_owner_truncate.value) == "55000"
                assert (
                    owner_connection.scalar(
                        text(
                            "SELECT count(*) FROM infrastructure_metrics "
                            "WHERE id = :metric_id"
                        ),
                        {"metric_id": metric_a},
                    )
                    == 1
                )
        # A suspended user must lose direct runtime-role visibility even when
        # the transaction-local tenant/user context is still supplied.
        with migrator_engine.begin() as connection:
            connection.execute(
                text("UPDATE users SET is_active = false WHERE id = :user_id"),
                {"user_id": user_a},
            )

        with runtime_engine.connect() as connection:
            with connection.begin():
                _set_context(connection, organization_a, user_a)
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM infrastructure_metrics "
                            "WHERE id = :metric_id"
                        ),
                        {"metric_id": metric_a},
                    )
                    == 0
                )
                _assert_metric_insert_denied(connection, organization_a, asset_a)

        # Membership revocation is represented by deleting the membership row.
        # Restore the account, revoke only its tenant membership, then prove that
        # the same runtime context no longer exposes the persisted metric.
        with migrator_engine.begin() as connection:
            connection.execute(
                text("UPDATE users SET is_active = true WHERE id = :user_id"),
                {"user_id": user_a},
            )
            connection.execute(
                text("DELETE FROM memberships WHERE id = :membership_id"),
                {"membership_id": membership_a},
            )

        with runtime_engine.connect() as connection:
            with connection.begin():
                _set_context(connection, organization_a, user_a)
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM infrastructure_metrics "
                            "WHERE id = :metric_id"
                        ),
                        {"metric_id": metric_a},
                    )
                    == 0
                )
                _assert_metric_insert_denied(connection, organization_a, asset_a)

    finally:
        runtime_engine.dispose()
        migrator_engine.dispose()
