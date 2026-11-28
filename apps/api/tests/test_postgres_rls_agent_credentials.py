"""PostgreSQL RLS checks for asset-scoped agent credentials."""

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


def _set_member_context(connection, organization_id, user_id) -> None:
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


def _set_agent_context(connection, token_hash: str) -> None:
    connection.execute(
        text("SELECT set_config('app.current_agent_token_hash', :token_hash, true)"),
        {"token_hash": token_hash},
    )


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)


def test_agent_credentials_enforce_member_and_single_token_rls() -> None:
    """The runtime sees one token row or one active tenant, never the table."""
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
    credential_a = uuid4()
    credential_b = uuid4()
    token_hash_a = "a" * 64
    token_hash_b = "b" * 64

    try:
        with migrator_engine.begin() as connection:
            assert connection.scalar(text("SELECT current_user")) == migrator_role
            flags = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = :role"
                ),
                {"role": runtime_role},
            ).one()
            assert flags.rolsuper is False
            assert flags.rolbypassrls is False

            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, :name, :slug)"
                ),
                [
                    {
                        "id": organization_a,
                        "name": f"Agent A {suffix}",
                        "slug": f"agent-a-{suffix}",
                    },
                    {
                        "id": organization_b,
                        "name": f"Agent B {suffix}",
                        "slug": f"agent-b-{suffix}",
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
                        "email": f"agent-a-{suffix}@example.test",
                        "display_name": "Agent Owner A",
                    },
                    {
                        "id": user_b,
                        "email": f"agent-b-{suffix}@example.test",
                        "display_name": "Agent Owner B",
                    },
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO roles "
                    "(id, organization_id, name, description, is_system) "
                    "VALUES (:id, :organization_id, 'owner', 'Agent test owner', true)"
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

            _set_member_context(connection, organization_a, user_a)
            connection.execute(
                text(
                    "INSERT INTO infrastructure_assets "
                    "(id, organization_id, name, asset_type) "
                    "VALUES (:id, :organization_id, 'Agent asset A', 'server')"
                ),
                {"id": asset_a, "organization_id": organization_a},
            )
            connection.execute(
                text(
                    "INSERT INTO infrastructure_agent_credentials "
                    "(id, organization_id, asset_id, created_by_user_id, name, "
                    "token_hash, token_prefix, expires_at) "
                    "VALUES (:id, :organization_id, :asset_id, :user_id, "
                    "'agent-a', :token_hash, 'eii_agent_a', now() + interval '1 day')"
                ),
                {
                    "id": credential_a,
                    "organization_id": organization_a,
                    "asset_id": asset_a,
                    "user_id": user_a,
                    "token_hash": token_hash_a,
                },
            )

            _set_member_context(connection, organization_b, user_b)
            connection.execute(
                text(
                    "INSERT INTO infrastructure_assets "
                    "(id, organization_id, name, asset_type) "
                    "VALUES (:id, :organization_id, 'Agent asset B', 'server')"
                ),
                {"id": asset_b, "organization_id": organization_b},
            )
            connection.execute(
                text(
                    "INSERT INTO infrastructure_agent_credentials "
                    "(id, organization_id, asset_id, created_by_user_id, name, "
                    "token_hash, token_prefix, expires_at) "
                    "VALUES (:id, :organization_id, :asset_id, :user_id, "
                    "'agent-b', :token_hash, 'eii_agent_b', now() + interval '1 day')"
                ),
                {
                    "id": credential_b,
                    "organization_id": organization_b,
                    "asset_id": asset_b,
                    "user_id": user_b,
                    "token_hash": token_hash_b,
                },
            )

        with runtime_engine.connect() as connection:
            with connection.begin():
                assert connection.scalar(text("SELECT current_user")) == runtime_role
                assert (
                    connection.scalar(
                        text("SELECT count(*) FROM infrastructure_agent_credentials")
                    )
                    == 0
                )

            with connection.begin():
                _set_agent_context(connection, token_hash_a)
                assert connection.scalars(
                    text(
                        "SELECT id FROM infrastructure_agent_credentials "
                        "WHERE token_hash = :token_hash"
                    ),
                    {"token_hash": token_hash_a},
                ).all() == [credential_a]
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM infrastructure_agent_credentials "
                            "WHERE token_hash = :token_hash"
                        ),
                        {"token_hash": token_hash_b},
                    )
                    == 0
                )

            with connection.begin():
                _set_member_context(connection, organization_a, user_a)
                assert connection.scalars(
                    text("SELECT id FROM infrastructure_agent_credentials")
                ).all() == [credential_a]

                with pytest.raises(DBAPIError) as denied_insert:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "INSERT INTO infrastructure_agent_credentials "
                                "(id, organization_id, asset_id, created_by_user_id, "
                                "name, token_hash, token_prefix, expires_at) "
                                "VALUES (:id, :organization_id, :asset_id, :user_id, "
                                "'foreign-agent', :token_hash, 'eii_agent_x', "
                                "now() + interval '1 day')"
                            ),
                            {
                                "id": uuid4(),
                                "organization_id": organization_b,
                                "asset_id": asset_b,
                                "user_id": user_a,
                                "token_hash": "c" * 64,
                            },
                        )
                assert _sqlstate(denied_insert.value) == "42501"

                with pytest.raises(DBAPIError) as denied_mutation:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "UPDATE infrastructure_agent_credentials "
                                "SET token_hash = :new_hash WHERE id = :id"
                            ),
                            {"new_hash": "d" * 64, "id": credential_a},
                        )
                assert _sqlstate(denied_mutation.value) == "55000"

                connection.execute(
                    text(
                        "UPDATE infrastructure_agent_credentials "
                        "SET revoked_at = now() WHERE id = :id"
                    ),
                    {"id": credential_a},
                )

                denied_delete = connection.execute(
                    text("DELETE FROM infrastructure_agent_credentials WHERE id = :id"),
                    {"id": credential_a},
                )
                assert denied_delete.rowcount == 0

                with pytest.raises(DBAPIError) as denied_unrevoke:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                "UPDATE infrastructure_agent_credentials "
                                "SET revoked_at = NULL WHERE id = :id"
                            ),
                            {"id": credential_a},
                        )
                assert _sqlstate(denied_unrevoke.value) == "55000"

            with connection.begin():
                _set_agent_context(connection, token_hash_a)
                assert (
                    connection.scalar(
                        text(
                            "SELECT count(*) FROM infrastructure_agent_credentials "
                            "WHERE token_hash = :token_hash"
                        ),
                        {"token_hash": token_hash_a},
                    )
                    == 0
                )

        with migrator_engine.begin() as connection:
            with pytest.raises(DBAPIError) as denied_truncate:
                with connection.begin_nested():
                    connection.execute(
                        text("TRUNCATE infrastructure_agent_credentials")
                    )
            assert _sqlstate(denied_truncate.value) == "55000"
    finally:
        runtime_engine.dispose()
        migrator_engine.dispose()
