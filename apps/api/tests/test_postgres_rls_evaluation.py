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


def test_trusted_transaction_context_rejects_caller_settable_guc_forgery() -> None:
    """A GUC alone cannot select a tenant without a DB-validated transaction lock."""
    import hashlib
    from datetime import datetime, timedelta, timezone

    database_url = os.environ.get("DATABASE_URL")
    assert database_url, "DATABASE_URL must target the ephemeral PostgreSQL service."

    engine = create_engine(
        database_url,
        pool_size=2,
        max_overflow=0,
        pool_pre_ping=True,
    )
    suffix = uuid4().hex
    schema = f"eii_trusted_rls_{suffix}"
    owner_role = f"eii_trusted_owner_{suffix}"
    runtime_role = f"eii_trusted_runtime_{suffix}"

    organization_a = uuid4()
    organization_b = uuid4()
    organization_deleted = uuid4()
    user_a = uuid4()
    user_b = uuid4()
    user_inactive_membership = uuid4()
    user_inactive = uuid4()
    user_deleted = uuid4()
    user_deleted_organization = uuid4()
    token_a = f"eii-test-session-a-{suffix}"
    token_b = f"eii-test-session-b-{suffix}"
    expired_token = f"eii-test-session-expired-{suffix}"
    revoked_token = f"eii-test-session-revoked-{suffix}"
    inactive_membership_token = f"eii-test-session-inactive-membership-{suffix}"
    inactive_user_token = f"eii-test-session-inactive-user-{suffix}"
    deleted_user_token = f"eii-test-session-deleted-user-{suffix}"
    deleted_organization_token = f"eii-test-session-deleted-organization-{suffix}"
    now = datetime.now(timezone.utc)

    def token_hash(token: str) -> bytes:
        return hashlib.sha256(token.encode("utf-8")).digest()

    def sqlstate(error: DBAPIError) -> str | None:
        return getattr(error.orig, "sqlstate", None) or getattr(
            error.orig, "pgcode", None
        )

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public"
            )
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
                f"""
                CREATE TABLE "{schema}".context_keys (
                    singleton boolean PRIMARY KEY CHECK (singleton),
                    secret bytea NOT NULL
                )
                """
            )
            connection.exec_driver_sql(
                f"""
                INSERT INTO "{schema}".context_keys (singleton, secret)
                VALUES (true, public.gen_random_bytes(32))
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE TABLE "{schema}".organizations (
                    id uuid PRIMARY KEY,
                    deleted_at timestamptz
                )
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE TABLE "{schema}".users (
                    id uuid PRIMARY KEY,
                    is_active boolean NOT NULL,
                    deleted_at timestamptz
                )
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE TABLE "{schema}".memberships (
                    organization_id uuid NOT NULL,
                    user_id uuid NOT NULL,
                    is_active boolean NOT NULL,
                    PRIMARY KEY (organization_id, user_id)
                )
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE TABLE "{schema}".sessions (
                    token_hash bytea PRIMARY KEY,
                    organization_id uuid NOT NULL,
                    user_id uuid NOT NULL,
                    expires_at timestamptz NOT NULL,
                    revoked_at timestamptz
                )
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE TABLE "{schema}".tenant_records (
                    organization_id uuid NOT NULL,
                    payload text NOT NULL
                )
                """
            )
            connection.execute(
                text(
                    f'INSERT INTO "{schema}".organizations (id, deleted_at) '
                    "VALUES (:org_a, NULL), (:org_b, NULL), "
                    "(:org_deleted, :deleted)"
                ),
                {
                    "org_a": organization_a,
                    "org_b": organization_b,
                    "org_deleted": organization_deleted,
                    "deleted": now,
                },
            )
            connection.execute(
                text(
                    f'INSERT INTO "{schema}".users (id, is_active, deleted_at) '
                    "VALUES "
                    "(:user_a, true, NULL), (:user_b, true, NULL), "
                    "(:user_inactive_membership, true, NULL), "
                    "(:user_inactive, false, NULL), "
                    "(:user_deleted, true, :deleted), "
                    "(:user_deleted_organization, true, NULL)"
                ),
                {
                    "user_a": user_a,
                    "user_b": user_b,
                    "user_inactive_membership": user_inactive_membership,
                    "user_inactive": user_inactive,
                    "user_deleted": user_deleted,
                    "user_deleted_organization": user_deleted_organization,
                    "deleted": now,
                },
            )
            connection.execute(
                text(
                    f'INSERT INTO "{schema}".memberships '
                    "(organization_id, user_id, is_active) "
                    "VALUES "
                    "(:org_a, :user_a, true), (:org_b, :user_b, true), "
                    "(:org_a, :user_inactive_membership, false), "
                    "(:org_a, :user_inactive, true), "
                    "(:org_a, :user_deleted, true), "
                    "(:org_deleted, :user_deleted_organization, true)"
                ),
                {
                    "org_a": organization_a,
                    "user_a": user_a,
                    "org_b": organization_b,
                    "user_b": user_b,
                    "user_inactive_membership": user_inactive_membership,
                    "user_inactive": user_inactive,
                    "user_deleted": user_deleted,
                    "org_deleted": organization_deleted,
                    "user_deleted_organization": user_deleted_organization,
                },
            )
            connection.execute(
                text(
                    f'INSERT INTO "{schema}".sessions '
                    "(token_hash, organization_id, user_id, expires_at, revoked_at) "
                    "VALUES "
                    "(:hash_a, :org_a, :user_a, :future, NULL), "
                    "(:hash_b, :org_b, :user_b, :future, NULL), "
                    "(:hash_expired, :org_a, :user_a, :past, NULL), "
                    "(:hash_revoked, :org_a, :user_a, :future, :revoked), "
                    "(:hash_inactive_membership, :org_a, :user_inactive_membership, :future, NULL), "
                    "(:hash_inactive_user, :org_a, :user_inactive, :future, NULL), "
                    "(:hash_deleted_user, :org_a, :user_deleted, :future, NULL), "
                    "(:hash_deleted_organization, :org_deleted, :user_deleted_organization, :future, NULL)"
                ),
                {
                    "hash_a": token_hash(token_a),
                    "hash_b": token_hash(token_b),
                    "hash_expired": token_hash(expired_token),
                    "hash_revoked": token_hash(revoked_token),
                    "hash_inactive_membership": token_hash(inactive_membership_token),
                    "hash_inactive_user": token_hash(inactive_user_token),
                    "hash_deleted_user": token_hash(deleted_user_token),
                    "hash_deleted_organization": token_hash(deleted_organization_token),
                    "org_a": organization_a,
                    "org_deleted": organization_deleted,
                    "user_inactive_membership": user_inactive_membership,
                    "user_inactive": user_inactive,
                    "user_deleted": user_deleted,
                    "user_deleted_organization": user_deleted_organization,
                    "user_a": user_a,
                    "org_b": organization_b,
                    "user_b": user_b,
                    "future": now + timedelta(hours=1),
                    "past": now - timedelta(minutes=1),
                    "revoked": now,
                },
            )
            connection.execute(
                text(
                    f'INSERT INTO "{schema}".tenant_records '
                    "(organization_id, payload) "
                    "VALUES (:org_a, 'tenant-a'), (:org_b, 'tenant-b')"
                ),
                {"org_a": organization_a, "org_b": organization_b},
            )

            # The private HMAC key never leaves this ephemeral database. The
            # runtime role receives EXECUTE on narrow functions, not table access.
            connection.exec_driver_sql(
                f"""
                CREATE FUNCTION "{schema}".trusted_context_valid(
                    p_organization_id uuid,
                    p_user_id uuid
                ) RETURNS boolean
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = pg_catalog
                AS $function$
                DECLARE
                    v_secret bytea;
                    v_mac bytea;
                    v_high bigint;
                    v_low bigint;
                    v_high_oid bigint;
                    v_low_oid bigint;
                BEGIN
                    IF p_organization_id IS NULL OR p_user_id IS NULL THEN
                        RETURN false;
                    END IF;

                    SELECT secret INTO v_secret
                    FROM "{schema}".context_keys
                    WHERE singleton = true;
                    IF v_secret IS NULL THEN
                        RETURN false;
                    END IF;

                    v_mac := public.hmac(
                        pg_catalog.convert_to(
                            p_organization_id::text || ':' ||
                            p_user_id::text || ':' ||
                            pg_catalog.pg_backend_pid()::text || ':' ||
                            pg_catalog.pg_current_xact_id()::text,
                            'UTF8'
                        ),
                        v_secret,
                        'sha256'
                    );
                    v_high :=
                        pg_catalog.get_byte(v_mac, 0)::bigint * 16777216 +
                        pg_catalog.get_byte(v_mac, 1)::bigint * 65536 +
                        pg_catalog.get_byte(v_mac, 2)::bigint * 256 +
                        pg_catalog.get_byte(v_mac, 3)::bigint;
                    v_low :=
                        pg_catalog.get_byte(v_mac, 4)::bigint * 16777216 +
                        pg_catalog.get_byte(v_mac, 5)::bigint * 65536 +
                        pg_catalog.get_byte(v_mac, 6)::bigint * 256 +
                        pg_catalog.get_byte(v_mac, 7)::bigint;
                    IF v_high >= 2147483648 THEN
                        v_high := v_high - 4294967296;
                    END IF;
                    IF v_low >= 2147483648 THEN
                        v_low := v_low - 4294967296;
                    END IF;
                    v_high_oid := CASE
                        WHEN v_high < 0 THEN v_high + 4294967296
                        ELSE v_high
                    END;
                    v_low_oid := CASE
                        WHEN v_low < 0 THEN v_low + 4294967296
                        ELSE v_low
                    END;

                    RETURN EXISTS (
                        SELECT 1
                        FROM pg_catalog.pg_locks AS lock_row
                        WHERE lock_row.locktype = 'advisory'
                          AND lock_row.pid = pg_catalog.pg_backend_pid()
                          AND lock_row.granted
                          AND lock_row.objsubid = 2
                          AND lock_row.classid::bigint = v_high_oid
                          AND lock_row.objid::bigint = v_low_oid
                    );
                END
                $function$
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE FUNCTION "{schema}".set_tenant_context(
                    p_session_token text
                ) RETURNS void
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = pg_catalog
                AS $function$
                DECLARE
                    v_organization_id uuid;
                    v_user_id uuid;
                    v_secret bytea;
                    v_mac bytea;
                    v_high bigint;
                    v_low bigint;
                BEGIN
                    SELECT session_row.organization_id, session_row.user_id
                    INTO v_organization_id, v_user_id
                    FROM "{schema}".sessions AS session_row
                    JOIN "{schema}".organizations AS organization_row
                      ON organization_row.id = session_row.organization_id
                     AND organization_row.deleted_at IS NULL
                    JOIN "{schema}".users AS user_row
                      ON user_row.id = session_row.user_id
                     AND user_row.is_active
                     AND user_row.deleted_at IS NULL
                    JOIN "{schema}".memberships AS membership_row
                      ON membership_row.organization_id =
                         session_row.organization_id
                     AND membership_row.user_id = session_row.user_id
                     AND membership_row.is_active
                    WHERE session_row.token_hash = public.digest(
                        pg_catalog.convert_to(p_session_token, 'UTF8'),
                        'sha256'
                    )
                      AND session_row.revoked_at IS NULL
                      AND session_row.expires_at > pg_catalog.clock_timestamp();

                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'invalid or inactive tenant session'
                            USING ERRCODE = '28000';
                    END IF;

                    SELECT secret INTO v_secret
                    FROM "{schema}".context_keys
                    WHERE singleton = true;
                    IF v_secret IS NULL THEN
                        RAISE EXCEPTION 'trusted context key is unavailable'
                            USING ERRCODE = '55000';
                    END IF;

                    v_mac := public.hmac(
                        pg_catalog.convert_to(
                            v_organization_id::text || ':' ||
                            v_user_id::text || ':' ||
                            pg_catalog.pg_backend_pid()::text || ':' ||
                            pg_catalog.pg_current_xact_id()::text,
                            'UTF8'
                        ),
                        v_secret,
                        'sha256'
                    );
                    v_high :=
                        pg_catalog.get_byte(v_mac, 0)::bigint * 16777216 +
                        pg_catalog.get_byte(v_mac, 1)::bigint * 65536 +
                        pg_catalog.get_byte(v_mac, 2)::bigint * 256 +
                        pg_catalog.get_byte(v_mac, 3)::bigint;
                    v_low :=
                        pg_catalog.get_byte(v_mac, 4)::bigint * 16777216 +
                        pg_catalog.get_byte(v_mac, 5)::bigint * 65536 +
                        pg_catalog.get_byte(v_mac, 6)::bigint * 256 +
                        pg_catalog.get_byte(v_mac, 7)::bigint;
                    IF v_high >= 2147483648 THEN
                        v_high := v_high - 4294967296;
                    END IF;
                    IF v_low >= 2147483648 THEN
                        v_low := v_low - 4294967296;
                    END IF;

                    PERFORM pg_catalog.pg_advisory_xact_lock(
                        v_high::integer,
                        v_low::integer
                    );
                    PERFORM pg_catalog.set_config(
                        'app.current_organization_id',
                        v_organization_id::text,
                        true
                    );
                    PERFORM pg_catalog.set_config(
                        'app.current_user_id',
                        v_user_id::text,
                        true
                    );
                END
                $function$
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE FUNCTION "{schema}".current_organization_id()
                RETURNS uuid
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = pg_catalog
                AS $function$
                DECLARE
                    v_organization_id uuid;
                    v_user_id uuid;
                BEGIN
                    v_organization_id := NULLIF(
                        pg_catalog.current_setting(
                            'app.current_organization_id', true
                        ),
                        ''
                    )::uuid;
                    v_user_id := NULLIF(
                        pg_catalog.current_setting('app.current_user_id', true),
                        ''
                    )::uuid;
                    IF "{schema}".trusted_context_valid(
                        v_organization_id, v_user_id
                    ) THEN
                        RETURN v_organization_id;
                    END IF;
                    RETURN NULL;
                EXCEPTION
                    WHEN invalid_text_representation THEN
                        RETURN NULL;
                END
                $function$
                """
            )
            connection.exec_driver_sql(
                f"""
                CREATE FUNCTION "{schema}".current_user_id()
                RETURNS uuid
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = pg_catalog
                AS $function$
                DECLARE
                    v_organization_id uuid;
                    v_user_id uuid;
                BEGIN
                    v_organization_id := NULLIF(
                        pg_catalog.current_setting(
                            'app.current_organization_id', true
                        ),
                        ''
                    )::uuid;
                    v_user_id := NULLIF(
                        pg_catalog.current_setting('app.current_user_id', true),
                        ''
                    )::uuid;
                    IF "{schema}".trusted_context_valid(
                        v_organization_id, v_user_id
                    ) THEN
                        RETURN v_user_id;
                    END IF;
                    RETURN NULL;
                EXCEPTION
                    WHEN invalid_text_representation THEN
                        RETURN NULL;
                END
                $function$
                """
            )
            connection.exec_driver_sql(
                f'ALTER TABLE "{schema}".tenant_records ' "ENABLE ROW LEVEL SECURITY"
            )
            connection.exec_driver_sql(
                f'ALTER TABLE "{schema}".tenant_records ' "FORCE ROW LEVEL SECURITY"
            )
            connection.exec_driver_sql(
                f"""
                CREATE POLICY trusted_tenant_isolation
                ON "{schema}".tenant_records
                USING (
                    organization_id = "{schema}".current_organization_id()
                )
                WITH CHECK (
                    organization_id = "{schema}".current_organization_id()
                )
                """
            )
            connection.exec_driver_sql("RESET ROLE")
            connection.exec_driver_sql(
                f'GRANT USAGE ON SCHEMA "{schema}" TO "{runtime_role}"'
            )
            connection.exec_driver_sql(
                f"GRANT SELECT, INSERT, UPDATE, DELETE "
                f'ON "{schema}".tenant_records TO "{runtime_role}"'
            )
            connection.exec_driver_sql(
                f'REVOKE ALL ON ALL TABLES IN SCHEMA "{schema}" FROM PUBLIC'
            )
            for signature in (
                f'"{schema}".trusted_context_valid(uuid, uuid)',
                f'"{schema}".set_tenant_context(text)',
                f'"{schema}".current_organization_id()',
                f'"{schema}".current_user_id()',
            ):
                connection.exec_driver_sql(
                    f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC"
                )
            connection.exec_driver_sql(
                f'GRANT EXECUTE ON FUNCTION "{schema}".set_tenant_context(text) '
                f'TO "{runtime_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT EXECUTE ON FUNCTION "{schema}".current_organization_id() '
                f'TO "{runtime_role}"'
            )
            connection.exec_driver_sql(
                f'GRANT EXECUTE ON FUNCTION "{schema}".current_user_id() '
                f'TO "{runtime_role}"'
            )

            flags = connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls FROM pg_catalog.pg_roles "
                    "WHERE rolname = :role"
                ),
                {"role": runtime_role},
            ).one()
            assert flags.rolsuper is False
            assert flags.rolbypassrls is False

            # The runtime role must not inherit or assume the function owner.
            owner_membership = connection.scalar(
                text(
                    "SELECT pg_catalog.pg_has_role("
                    "CAST(:member_role AS name), CAST(:target_role AS name), "
                    "'MEMBER')"
                ),
                {"member_role": runtime_role, "target_role": owner_role},
            )
            assert owner_membership is False

        with engine.connect() as connection:
            # A caller can set arbitrary custom GUCs, but without the private
            # transaction lock the policy remains default-deny.
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                connection.execute(
                    text(
                        "SELECT pg_catalog.set_config("
                        "'app.current_organization_id', :org, true), "
                        "pg_catalog.set_config('app.current_user_id', :user, true)"
                    ),
                    {"org": str(organization_b), "user": str(user_b)},
                )
                assert (
                    connection.scalar(
                        text(f'SELECT "{schema}".current_organization_id()')
                    )
                    is None
                )
                assert (
                    connection.scalar(
                        text(f'SELECT count(*) FROM "{schema}".tenant_records')
                    )
                    == 0
                )

                with pytest.raises(DBAPIError) as denied_private_read:
                    with connection.begin_nested():
                        connection.execute(
                            text(f'SELECT secret FROM "{schema}".context_keys')
                        )
                assert sqlstate(denied_private_read.value) == "42501"

                with pytest.raises(DBAPIError) as denied_private_session_read:
                    with connection.begin_nested():
                        connection.execute(
                            text(f'SELECT token_hash FROM "{schema}".sessions')
                        )
                assert sqlstate(denied_private_session_read.value) == "42501"

                with pytest.raises(DBAPIError) as denied_internal_helper:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                f'SELECT "{schema}".trusted_context_valid('
                                ":organization_id, :user_id)"
                            ),
                            {
                                "organization_id": organization_a,
                                "user_id": user_a,
                            },
                        )
                assert sqlstate(denied_internal_helper.value) == "42501"

            # A validated session creates a lock scoped to this backend and
            # transaction. Changing either GUC cannot retarget that lock.
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                connection.execute(
                    text(f'SELECT "{schema}".set_tenant_context(:token)'),
                    {"token": token_a},
                )
                assert str(
                    connection.scalar(
                        text(f'SELECT "{schema}".current_organization_id()')
                    )
                ) == str(organization_a)
                assert str(
                    connection.scalar(text(f'SELECT "{schema}".current_user_id()'))
                ) == str(user_a)
                assert connection.scalars(
                    text(
                        f'SELECT payload FROM "{schema}".tenant_records '
                        "ORDER BY payload"
                    )
                ).all() == ["tenant-a"]

                connection.execute(
                    text(
                        "SELECT pg_catalog.set_config("
                        "'app.current_organization_id', :org, true), "
                        "pg_catalog.set_config('app.current_user_id', :user, true)"
                    ),
                    {"org": str(organization_b), "user": str(user_b)},
                )
                assert (
                    connection.scalar(
                        text(f'SELECT "{schema}".current_organization_id()')
                    )
                    is None
                )
                assert (
                    connection.scalar(
                        text(f'SELECT count(*) FROM "{schema}".tenant_records')
                    )
                    == 0
                )
                with pytest.raises(DBAPIError) as denied_cross_tenant_insert:
                    with connection.begin_nested():
                        connection.execute(
                            text(
                                f'INSERT INTO "{schema}".tenant_records '
                                "(organization_id, payload) "
                                "VALUES (:org, 'forged-tenant-b')"
                            ),
                            {"org": organization_b},
                        )
                assert sqlstate(denied_cross_tenant_insert.value) == "42501"

                # Restoring the original, validated identity restores only A.
                connection.execute(
                    text(
                        "SELECT pg_catalog.set_config("
                        "'app.current_organization_id', :org, true), "
                        "pg_catalog.set_config('app.current_user_id', :user, true)"
                    ),
                    {"org": str(organization_a), "user": str(user_a)},
                )
                assert connection.scalars(
                    text(
                        f'SELECT payload FROM "{schema}".tenant_records '
                        "ORDER BY payload"
                    )
                ).all() == ["tenant-a"]

            # Transaction-level locks and SET LOCAL values do not survive commit.
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                connection.execute(
                    text(
                        "SELECT pg_catalog.set_config("
                        "'app.current_organization_id', :org, true), "
                        "pg_catalog.set_config('app.current_user_id', :user, true)"
                    ),
                    {"org": str(organization_a), "user": str(user_a)},
                )
                assert (
                    connection.scalar(
                        text(f'SELECT "{schema}".current_organization_id()')
                    )
                    is None
                )
                assert (
                    connection.scalar(
                        text(f'SELECT count(*) FROM "{schema}".tenant_records')
                    )
                    == 0
                )

            # Expired and revoked sessions cannot mint a context lock.
            for token in (
                expired_token,
                revoked_token,
                inactive_membership_token,
                inactive_user_token,
                deleted_user_token,
                deleted_organization_token,
            ):
                with connection.begin():
                    connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                    with pytest.raises(DBAPIError) as denied_session:
                        with connection.begin_nested():
                            connection.execute(
                                text(f'SELECT "{schema}".set_tenant_context(:token)'),
                                {"token": token},
                            )
                    assert sqlstate(denied_session.value) == "28000"
                    connection.execute(
                        text(
                            "SELECT pg_catalog.set_config("
                            "'app.current_organization_id', :org, true), "
                            "pg_catalog.set_config('app.current_user_id', :user, true)"
                        ),
                        {"org": str(organization_a), "user": str(user_a)},
                    )
                    assert (
                        connection.scalar(
                            text(f'SELECT count(*) FROM "{schema}".tenant_records')
                        )
                        == 0
                    )

            # A second backend cannot reuse the first backend's valid context.
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                connection.execute(
                    text(f'SELECT "{schema}".set_tenant_context(:token)'),
                    {"token": token_a},
                )
                assert (
                    connection.scalar(
                        text(f'SELECT count(*) FROM "{schema}".tenant_records')
                    )
                    == 1
                )
                with engine.connect() as second_connection:
                    with second_connection.begin():
                        second_connection.exec_driver_sql(
                            f'SET LOCAL ROLE "{runtime_role}"'
                        )
                        second_connection.execute(
                            text(
                                "SELECT pg_catalog.set_config("
                                "'app.current_organization_id', :org, true), "
                                "pg_catalog.set_config('app.current_user_id', :user, true)"
                            ),
                            {"org": str(organization_a), "user": str(user_a)},
                        )
                        assert (
                            second_connection.scalar(
                                text(f'SELECT "{schema}".current_organization_id()')
                            )
                            is None
                        )
                        assert (
                            second_connection.scalar(
                                text(f'SELECT count(*) FROM "{schema}".tenant_records')
                            )
                            == 0
                        )

            # A different valid session is authorized only for its own tenant.
            with connection.begin():
                connection.exec_driver_sql(f'SET LOCAL ROLE "{runtime_role}"')
                connection.execute(
                    text(f'SELECT "{schema}".set_tenant_context(:token)'),
                    {"token": token_b},
                )
                assert connection.scalars(
                    text(
                        f'SELECT payload FROM "{schema}".tenant_records '
                        "ORDER BY payload"
                    )
                ).all() == ["tenant-b"]
    finally:
        try:
            with engine.begin() as cleanup:
                cleanup.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                cleanup.exec_driver_sql(f'DROP ROLE IF EXISTS "{runtime_role}"')
                cleanup.exec_driver_sql(f'DROP ROLE IF EXISTS "{owner_role}"')
        finally:
            engine.dispose()
