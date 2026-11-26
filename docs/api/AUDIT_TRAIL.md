# P1-A5 — tenant audit trail foundation

## Delivered in this slice

- PostgreSQL migration `0006_audit_events` creates tenant-attributed audit events.
- Every event identifies an organization and an actor who has a membership in that same organization. A composite foreign key preserves this relationship.
- Event type, optional target, request ID, JSON details and UTC occurrence time are stored.
- PostgreSQL triggers reject `UPDATE`, `DELETE` and `TRUNCATE` on the event table.
- The migration refuses to downgrade while audit history exists; it does not silently discard records.
- The internal writer validates the active actor membership, rejects credential-like detail keys, requires a JSON object, caps details at 16 KiB and rejects container nesting deeper than 32 levels using iterative traversal. It flushes but never commits; the caller owns the transaction.
- The read endpoint is protected by the existing organization-scoped `audit.read` permission.

## API

`GET /api/v1/organizations/{organization_id}/audit-events?limit=50`

- Requires an active server session and membership in the requested organization.
- Requires `audit.read`; a non-member receives 404 and a member without permission receives 403.
- Returns newest events first. `limit` is between 1 and 100.
- The response contains event metadata only; it never returns passwords, session tokens, CSRF tokens, cookies or authorization headers.

## Important implementation boundary

This slice delivers the event schema, validated internal writer and protected read API. Existing organization, authentication and dashboard flows do not yet call the writer automatically. Therefore the endpoint may return an empty list until a later mutation workflow records events. No audit trail is claimed for operations that have not been instrumented.

RLS is not delivered by this change. The PostgreSQL append-only triggers protect ordinary row mutation paths, but a database superuser can disable triggers. The separate owner/migrator and non-superuser runtime-role prerequisite remains open and must be resolved before claiming database-enforced tenant isolation.

## Verification

- SQLite-backed service and HTTP tests cover tenant scoping, newest-first ordering, cross-tenant actor rejection, sensitive-field rejection, the 32/33-level nesting boundary, session enforcement, 403/404 behavior and pagination bounds.
- Compose smoke runs PostgreSQL-specific checks against a real migrated database: same-tenant insert succeeds; cross-tenant actor insert fails; update/delete/truncate are rejected; the test transaction rolls back before the downgrade cycle.
