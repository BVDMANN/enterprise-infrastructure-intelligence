# PostgreSQL development roles

The Compose stack separates database bootstrap, schema migration, and
application runtime connections.

| Role | Login | Purpose | Privilege boundary |
|---|---:|---|---|
| `eii` (configurable via `POSTGRES_USER`) | Yes | Official image bootstrap administrator | Superuser; only the DB healthcheck and bootstrap service receive it |
| `eii_migrator` | Yes | One-shot Alembic service | `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`; CREATE on the application database/schema |
| `eii_runtime` | Yes | API and Worker | `NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS`; CRUD on application tables and sequence usage |

The Compose `db-bootstrap` service creates/normalizes the two application
roles. The `migrate` service receives only `MIGRATION_DATABASE_URL` and
runs `alembic upgrade head`. The API and Worker receive only
`DATABASE_URL`, built from the runtime role. They do not receive the
bootstrap administrator or migration URL.

The migrator has CREATE on the database so the trusted `citext` extension
can be installed by the initial migration. It has CREATE on schema
`public`; future tables and sequences created by that role grant the
minimum runtime privileges through ALTER DEFAULT PRIVILEGES. The bootstrap
script also grants privileges on objects that already exist.

## Existing development volumes

For a fresh volume, migrations create objects as `eii_migrator`.

For a volume that already contains application tables owned by the old
bootstrap role, the default `EII_ADOPT_EXISTING_SCHEMA_OWNERSHIP=false`
does **not** change their owners. The one-shot migration can still inspect an
already-current schema, but a future migration that alters an old table will
need its ownership transferred.

Only after inspecting the volume and taking a recoverable backup, a developer
may explicitly set `EII_ADOPT_EXISTING_SCHEMA_OWNERSHIP=true` in their local
`.env`. The idempotent bootstrap then transfers ownership of existing
public tables and sequences to the migrator. This changes PostgreSQL object
ownership; it is not enabled by default and is not a production migration
procedure. Do not set it on a shared or production database without a
separately reviewed migration and recovery plan.

## Security boundaries and limitations

- All passwords in `.env.example` are development placeholders. Replace them
  locally; never commit a real `.env` or secret.
- Use URL-safe generated credentials or percent-encode reserved characters in
  PostgreSQL URLs.
- The bootstrap administrator is still a superuser by design. It is confined to
  the DB healthcheck/bootstrap path and explicit administrative or ephemeral CI
  smoke commands; it is not injected into API, Worker, or migration containers.
- This lot does not enable RLS on application tables and does not establish a
  trusted tenant context. The isolated RLS prototype remains an evaluation,
  not a production security guarantee.
- Runtime and migrator roles are both `NOBYPASSRLS`; future RLS adoption must
  add table policies, FORCE ROW LEVEL SECURITY where appropriate, and
  authenticated tenant-context tests on real API/Worker paths.
