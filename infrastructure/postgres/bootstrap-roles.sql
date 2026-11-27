\\set ON_ERROR_STOP on

-- Create the least-privilege roles when absent, then normalize their
-- attributes and development credentials on every idempotent bootstrap.
SELECT format(
    'CREATE ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
    :'runtime_role',
    :'runtime_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'runtime_role'
)
\\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
    :'runtime_role',
    :'runtime_password'
)
\\gexec

SELECT format(
    'CREATE ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
    :'migrator_role',
    :'migrator_password'
)
WHERE NOT EXISTS (
    SELECT 1 FROM pg_roles WHERE rolname = :'migrator_role'
)
\\gexec

SELECT format(
    'ALTER ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS',
    :'migrator_role',
    :'migrator_password'
)
\\gexec

-- Existing-volume ownership adoption is deliberately opt-in. It changes
-- object ownership but never deletes or rewrites application data.
\\if :adopt_existing_schema_ownership
SELECT format(
    'ALTER TABLE %I.%I OWNER TO %I',
    schemaname,
    tablename,
    :'migrator_role'
)
FROM pg_tables
WHERE schemaname = 'public'
  AND tableowner <> :'migrator_role'
\\gexec

SELECT format(
    'ALTER SEQUENCE %I.%I OWNER TO %I',
    namespace.nspname,
    sequence.relname,
    :'migrator_role'
)
FROM pg_class AS sequence
JOIN pg_namespace AS namespace
  ON namespace.oid = sequence.relnamespace
WHERE namespace.nspname = 'public'
  AND sequence.relkind = 'S'
  AND pg_get_userbyid(sequence.relowner) <> :'migrator_role'
\\gexec
\\endif

-- The bootstrap administrator remains the only superuser. The migrator can
-- install trusted extensions and create/alter application objects; it cannot
-- create databases/roles or bypass row-level security.
SELECT format(
    'GRANT CONNECT ON DATABASE %I TO %I',
    current_database(),
    :'runtime_role'
)
\\gexec

SELECT format(
    'GRANT CONNECT, CREATE ON DATABASE %I TO %I',
    current_database(),
    :'migrator_role'
)
\\gexec

SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'runtime_role')
\\gexec

SELECT format(
    'GRANT USAGE, CREATE ON SCHEMA public TO %I',
    :'migrator_role'
)
\\gexec

-- Existing objects receive explicit grants. New objects created by Alembic
-- inherit the runtime grants through the migrator's default privileges.
SELECT format(
    'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I',
    :'runtime_role'
)
\\gexec

SELECT format(
    'GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO %I',
    :'migrator_role'
)
\\gexec

SELECT format(
    'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO %I',
    :'runtime_role'
)
\\gexec

SELECT format(
    'GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO %I',
    :'migrator_role'
)
\\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
    'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
    :'migrator_role',
    :'runtime_role'
)
\\gexec

SELECT format(
    'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
    'GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
    :'migrator_role',
    :'runtime_role'
)
\\gexec

\\echo 'PostgreSQL runtime and migrator roles are provisioned.'
