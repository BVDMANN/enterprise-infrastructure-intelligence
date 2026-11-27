"""PostgreSQL integration tests for least-privilege runtime/migrator roles."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.core.config import settings
from app.db.session import engine as runtime_engine

pytestmark = pytest.mark.skipif(
    os.getenv("EII_POSTGRES_ROLE_SEPARATION") != "1",
    reason="Requires the dedicated PostgreSQL role-separation job",
)


def _assert_non_privileged_role(connection) -> None:
    flags = connection.execute(
        text(
            "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
            "FROM pg_roles WHERE rolname = current_user"
        )
    ).one()
    assert tuple(flags) == (False, False, False, False)


def _assert_insufficient_privilege(error: DBAPIError, operation: str) -> None:
    sqlstate = getattr(error.orig, "sqlstate", None) or getattr(
        error.orig, "pgcode", None
    )
    assert sqlstate == "42501", (
        f"{operation} should fail with SQLSTATE 42501, got {sqlstate}"
    )


def test_runtime_role_has_crud_access_but_cannot_create_schema_objects() -> None:
    with runtime_engine.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == "eii_runtime"
        _assert_non_privileged_role(connection)
        assert connection.scalar(text("SELECT count(*) FROM organizations")) >= 0

    with runtime_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.exec_driver_sql(
                "CREATE TABLE public.eii_runtime_ddl_probe (id integer)"
            )
        except DBAPIError:
            transaction.rollback()
        else:
            transaction.rollback()
            pytest.fail("The runtime role unexpectedly created a schema object.")


def test_migrator_role_is_non_superuser_and_can_manage_schema_objects() -> None:
    migration_engine = create_engine(settings.alembic_database_url)
    try:
        with migration_engine.connect() as connection:
            assert connection.scalar(text("SELECT current_user")) == "eii_migrator"
            _assert_non_privileged_role(connection)

        with migration_engine.connect() as connection:
            transaction = connection.begin()
            connection.exec_driver_sql(
                "CREATE TABLE public.eii_migrator_ddl_probe (id integer)"
            )
            transaction.rollback()
    finally:
        migration_engine.dispose()


def test_runtime_role_can_insert_update_and_delete_migrator_created_rows() -> None:
    """Default privileges let the runtime perform DML on future Alembic objects."""
    migration_engine = create_engine(settings.alembic_database_url)
    table_name = f"eii_runtime_dml_probe_{uuid4().hex}"
    table_created = False
    probe_id = uuid4()

    try:
        # The migrator creates a fresh object so this also verifies ALTER DEFAULT
        # PRIVILEGES, not only grants on tables that existed during bootstrap.
        with migration_engine.begin() as connection:
            connection.exec_driver_sql(
                f"CREATE TABLE public.{table_name} "
                "(id uuid PRIMARY KEY, value text NOT NULL)"
            )
        table_created = True

        with runtime_engine.begin() as connection:
            connection.execute(
                text(
                    f"INSERT INTO public.{table_name} (id, value) "
                    "VALUES (:id, :value)"
                ),
                {"id": probe_id, "value": "created"},
            )
            updated_value = connection.execute(
                text(
                    f"UPDATE public.{table_name} SET value = :value "
                    "WHERE id = :id RETURNING value"
                ),
                {"id": probe_id, "value": "updated"},
            ).scalar_one()
            assert updated_value == "updated"

            deleted_id = connection.execute(
                text(f"DELETE FROM public.{table_name} WHERE id = :id RETURNING id"),
                {"id": probe_id},
            ).scalar_one()
            assert deleted_id == probe_id
            assert (
                connection.scalar(text(f"SELECT count(*) FROM public.{table_name}"))
                == 0
            )
    finally:
        if table_created:
            with migration_engine.begin() as connection:
                connection.exec_driver_sql(f"DROP TABLE IF EXISTS public.{table_name}")
        migration_engine.dispose()


def test_runtime_role_cannot_truncate_migrator_created_table() -> None:
    migration_engine = create_engine(settings.alembic_database_url)
    table_name = f"eii_runtime_truncate_probe_{uuid4().hex}"
    table_created = False

    try:
        with migration_engine.begin() as connection:
            connection.exec_driver_sql(
                f"CREATE TABLE public.{table_name} (id integer PRIMARY KEY)"
            )
            table_created = True
            connection.exec_driver_sql(
                f"INSERT INTO public.{table_name} (id) VALUES (1)"
            )

        with runtime_engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.exec_driver_sql(f"TRUNCATE TABLE public.{table_name}")
            except DBAPIError as error:
                transaction.rollback()
                _assert_insufficient_privilege(error, "runtime TRUNCATE")
            else:
                transaction.rollback()
                pytest.fail("The runtime role unexpectedly truncated a table.")

            assert (
                connection.scalar(text(f"SELECT count(*) FROM public.{table_name}"))
                == 1
            )
    finally:
        if table_created:
            with migration_engine.begin() as connection:
                connection.exec_driver_sql(f"DROP TABLE IF EXISTS public.{table_name}")
        migration_engine.dispose()


def test_migrator_cannot_create_roles_or_databases() -> None:
    migration_engine = create_engine(settings.alembic_database_url)
    role_name = f"eii_probe_role_{uuid4().hex}"
    database_name = f"eii_probe_db_{uuid4().hex}"
    database_created = False
    autocommit_engine = create_engine(
        settings.alembic_database_url,
        isolation_level="AUTOCOMMIT",
    )

    try:
        with migration_engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.exec_driver_sql(f"CREATE ROLE {role_name} LOGIN")
            except DBAPIError as error:
                transaction.rollback()
                _assert_insufficient_privilege(error, "migrator CREATE ROLE")
            else:
                transaction.rollback()
                pytest.fail("The migrator unexpectedly created a PostgreSQL role.")

        # CREATE DATABASE must run outside a transaction. If the privilege
        # boundary regresses, remove the uniquely named probe before failing.
        with autocommit_engine.connect() as connection:
            try:
                connection.exec_driver_sql(f"CREATE DATABASE {database_name}")
            except DBAPIError as error:
                _assert_insufficient_privilege(error, "migrator CREATE DATABASE")
            else:
                database_created = True
    finally:
        if database_created:
            with autocommit_engine.connect() as connection:
                connection.exec_driver_sql(f"DROP DATABASE {database_name}")
        autocommit_engine.dispose()
        migration_engine.dispose()

    if database_created:
        pytest.fail("The migrator unexpectedly created a PostgreSQL database.")
