#!/bin/sh
set -eu

: "${PGHOST:?PGHOST is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGUSER:?PGUSER must identify the bootstrap administrator}"
: "${PGPASSWORD:?PGPASSWORD is required}"
: "${EII_RUNTIME_ROLE:?EII_RUNTIME_ROLE is required}"
: "${EII_RUNTIME_PASSWORD:?EII_RUNTIME_PASSWORD is required}"
: "${EII_MIGRATOR_ROLE:?EII_MIGRATOR_ROLE is required}"
: "${EII_MIGRATOR_PASSWORD:?EII_MIGRATOR_PASSWORD is required}"

case "${EII_RUNTIME_ROLE}${EII_MIGRATOR_ROLE}" in
  *[!A-Za-z0-9_]*|'')
    echo "Role names must contain only ASCII letters, digits, and underscores." >&2
    exit 2
    ;;
esac

if [ "$EII_RUNTIME_ROLE" = "$EII_MIGRATOR_ROLE" ] \
  || [ "$EII_RUNTIME_ROLE" = "$PGUSER" ] \
  || [ "$EII_MIGRATOR_ROLE" = "$PGUSER" ]; then
  echo "Bootstrap admin, runtime, and migrator roles must be distinct." >&2
  exit 2
fi

adopt_existing="${EII_ADOPT_EXISTING_SCHEMA_OWNERSHIP:-false}"
case "$adopt_existing" in
  true|false) ;;
  *)
    echo "EII_ADOPT_EXISTING_SCHEMA_OWNERSHIP must be true or false." >&2
    exit 2
    ;;
esac

# psql reads role names and passwords from its environment via \\getenv;
# credentials are not placed in the psql process argument list.
psql --no-psqlrc --set=ON_ERROR_STOP=1 --file=/scripts/bootstrap-roles.sql
