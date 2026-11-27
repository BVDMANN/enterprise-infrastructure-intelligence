"""PostgreSQL integration tests for least-privilege runtime/migrator roles."""

from __future__ import annotations

import os

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
