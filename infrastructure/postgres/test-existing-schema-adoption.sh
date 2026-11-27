#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER must identify the bootstrap administrator}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${EII_RUNTIME_ROLE:?EII_RUNTIME_ROLE is required}"
: "${EII_RUNTIME_PASSWORD:?EII_RUNTIME_PASSWORD is required}"
: "${EII_MIGRATOR_ROLE:?EII_MIGRATOR_ROLE is required}"
: "${EII_MIGRATOR_PASSWORD:?EII_MIGRATOR_PASSWORD is required}"

probe_table="eii_legacy_adoption_$$"
probe_sequence="${probe_table}_sequence"

cleanup() {
  psql --no-psqlrc --set=ON_ERROR_STOP=1 \
    --set=probe_table="$probe_table" \
    --set=probe_sequence="$probe_sequence" <<'SQL' >/dev/null 2>&1 || true
DROP TABLE IF EXISTS public.:"probe_table";
DROP SEQUENCE IF EXISTS public.:"probe_sequence";
SQL
}
trap cleanup EXIT

psql --no-psqlrc --set=ON_ERROR_STOP=1 \
  --set=probe_table="$probe_table" \
  --set=probe_sequence="$probe_sequence" <<'SQL'
CREATE TABLE public.:"probe_table" (
    id integer PRIMARY KEY,
    value text NOT NULL
);
INSERT INTO public.:"probe_table" (id, value) VALUES (1, 'preserved');
CREATE SEQUENCE public.:"probe_sequence";
SQL

read_owners() {
  psql --no-psqlrc --tuples-only --no-align --quiet \
    --set=ON_ERROR_STOP=1 \
    --set=probe_table="$probe_table" \
    --set=probe_sequence="$probe_sequence" <<'SQL'
SELECT
    (SELECT tableowner
     FROM pg_tables
     WHERE schemaname = 'public' AND tablename = :'probe_table')
    || '|' ||
    (SELECT pg_get_userbyid(class.relowner)
     FROM pg_class AS class
     JOIN pg_namespace AS namespace ON namespace.oid = class.relnamespace
     WHERE namespace.nspname = 'public'
       AND class.relname = :'probe_sequence');
SQL
}

assert_owners() {
  expected="$1"
  actual=$(read_owners)
  if [ "$actual" != "$expected" ]; then
    echo "Expected probe owners '$expected', got '$actual'." >&2
    exit 1
  fi
}

assert_data_preserved() {
  row_count=$(psql --no-psqlrc --tuples-only --no-align --quiet \
    --set=ON_ERROR_STOP=1 \
    --set=probe_table="$probe_table" \
    -c 'SELECT count(*) FROM public.:"probe_table";')
  if [ "$row_count" != "1" ]; then
    echo "Expected the legacy row to remain present, got count '$row_count'." >&2
    exit 1
  fi
}

# The default/false mode must leave objects owned by the old bootstrap role.
EII_ADOPT_EXISTING_SCHEMA_OWNERSHIP=false "$script_dir/bootstrap-roles.sh"
assert_owners "$PGUSER|$PGUSER"
assert_data_preserved

# Explicit opt-in transfers both legacy tables and sequences to the migrator.
EII_ADOPT_EXISTING_SCHEMA_OWNERSHIP=true "$script_dir/bootstrap-roles.sh"
assert_owners "$EII_MIGRATOR_ROLE|$EII_MIGRATOR_ROLE"
assert_data_preserved

# Repeating the opt-in bootstrap must remain safe and preserve the data.
EII_ADOPT_EXISTING_SCHEMA_OWNERSHIP=true "$script_dir/bootstrap-roles.sh"
assert_owners "$EII_MIGRATOR_ROLE|$EII_MIGRATOR_ROLE"
assert_data_preserved

echo "Existing-schema ownership adoption: default preserved, opt-in transferred table/sequence, data preserved, repeat idempotent."
