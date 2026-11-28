# ADR-0007 — PostgreSQL Row-Level Security evaluation prototype

- **Status:** Accepted for partial application-table enforcement; full tenant-table rollout remains pending.
- **Date:** 2026-11-27.
- **Related:** ADR-0005, ADR-0006, P1-A1 identity, P1-A3 RBAC, P1-A5 audit trail.

## Context

The API already applies authenticated-session and organization-scoped RBAC checks.
PostgreSQL also enforces tenant consistency for memberships through a composite
foreign key, and audit events are tenant-attributed and append-only. These controls
do not constitute PostgreSQL Row-Level Security.

A production RLS rollout cannot safely be enabled on the current development
connection unchanged: docker-compose.yml defaults POSTGRES_USER to eii, and the
API DATABASE_URL uses that same bootstrap account. The official PostgreSQL image
creates POSTGRES_USER as a database superuser. Superusers bypass RLS, so adding
policies alone would provide no isolation for that connection.

## Evaluation scope

This proposal adds an isolated CI-only proof of PostgreSQL mechanics:

- A temporary schema with one tenant-keyed table; no application table or Alembic
  migration is modified.
- Separate temporary NOLOGIN, NOSUPERUSER, NOBYPASSRLS owner and runtime roles.
- ENABLE ROW LEVEL SECURITY plus FORCE ROW LEVEL SECURITY.
- A transaction-local app.current_organization_id setting used by both USING and
  WITH CHECK policies.
- Default-deny reads without a tenant context; tenant-specific reads; rejection
  of cross-tenant INSERT and UPDATE; and hidden cross-tenant DELETE.
- Verification that the table owner is also subject to FORCE ROW LEVEL SECURITY.
- Reuse of one pooled connection to verify SET LOCAL and the tenant setting do not
  leak into the next transaction.
- Cleanup of the temporary schema and roles in the ephemeral CI database.

The prototype is run by the dedicated PostgreSQL RLS evaluation job. It is not
part of the application's runtime path.

## Security limitations

A custom PostgreSQL setting is caller-settable by any database role allowed to
execute set_config for that setting. Therefore this prototype proves policy
mechanics and protects against omitted tenant predicates only when the application
sets context correctly; it does not make a compromised runtime role or arbitrary
SQL injection safe.

Before production adoption, a separate accepted ADR and implementation must:

1. Separate the migration/schema-owner role from a non-superuser application role
   with NOBYPASSRLS and least-privilege table grants.
2. Derive tenant context only after validating the authenticated user and active
   membership, and set it transaction-locally before any tenant-scoped query.
3. Define safe behavior for users belonging to multiple organizations, platform
   operations, support access, migrations, workers, scheduled tasks and connectors.
4. Test missing context, cross-tenant SELECT/INSERT/UPDATE/DELETE, role ownership,
   privilege escalation, rollback, connection-pool reuse and background jobs.
5. Keep application-layer authorization; RLS is an additional control, not its
   replacement.

## Phase 1 partial application rollout (2026-11-28)

Migration `0009_application_table_rls` enables and forces RLS on exactly two
real application tables:

- `infrastructure_assets`
- `audit_events`

The policy requires both transaction-local settings:
`app.current_organization_id` and `app.current_user_id`. It also checks
that the user has an active, non-deleted membership in that organization.
Missing or mismatched context is default-deny. The API sets context only after
session resolution and organization RBAC; the audit writer binds it to the
validated actor. The inventory service preserves the authenticated user
context. Context uses `set_config(..., true)` so it is cleared at transaction
end, including on pooled connection reuse.

The PostgreSQL integration test runs against the actual `eii_runtime` login
and migrated application tables. It checks table ownership, ENABLE/FORCE RLS,
missing-context denial, tenant A/B isolation, membership mismatch, cross-tenant
INSERT/UPDATE denial, hidden cross-tenant DELETE, and transaction cleanup.

This is deliberately a partial rollout. `organizations`, `users`,
`memberships`, `roles`, `role_permissions`, and `invitations` are not yet
protected by RLS; their existing application-layer session/RBAC checks remain
in force. Background workers and future collectors must establish an explicit
validated tenant/user context before accessing the two protected tables.

A custom PostgreSQL GUC is settable by the connected runtime role. Therefore
this rollout protects against omitted tenant predicates when the application
context setter is used correctly, but it is not a boundary against arbitrary
SQL execution, SQL injection, or a compromised runtime credential. Keep
parameterized SQL, application authorization, least-privilege grants, and
independent security review. Do not describe this as complete database-level
tenant isolation.

## Decision boundary

This proposal does not enable RLS on organizations, users, memberships, roles or
audit_events. It does not change docker-compose credentials, application
DATABASE_URL, production roles, migrations or data. Production adoption remains
open until the security model and operational role separation receive independent
review.
