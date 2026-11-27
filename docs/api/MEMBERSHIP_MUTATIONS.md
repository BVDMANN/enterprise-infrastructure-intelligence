# Tenant membership lifecycle API

These P1-A5 endpoints mutate organization memberships and append tenant-scoped audit events in the same database transaction.

## Add an existing user

`POST /api/v1/organizations/{organization_id}/memberships`

Request:

```json
{
  "user_id": "existing-user-uuid",
  "role_id": "role-uuid-from-the-same-organization"
}
```

Returns HTTP 201 with the membership UUID, user UUID, role UUID and creation timestamp. The existing `GET /api/v1/organizations/{organization_id}/members` response also exposes `membership_id`, so authorized clients can address a specific membership without guessing or reusing a user ID.

## Change a membership role

`PATCH /api/v1/organizations/{organization_id}/memberships/{membership_id}`

Request:

```json
{
  "role_id": "new-role-uuid-from-the-same-organization"
}
```

Returns HTTP 200 with the membership identifiers and creation timestamp. The membership and selected role are both resolved inside the path organization. A role from another organization is not accepted. Repeating the current role is an idempotent no-op and does not create a duplicate audit event.

## Remove a membership

`DELETE /api/v1/organizations/{organization_id}/memberships/{membership_id}`

Returns HTTP 204 after the membership is removed and its audit event is committed. Self-removal returns HTTP 409: the audit schema requires the event actor to remain an active member of the organization, so another authorized owner/admin must remove that membership.

A membership ID belonging to another organization is indistinguishable from a missing membership and returns HTTP 404.

## Authorization and CSRF

All three mutations require:

1. a live server-side session;
2. an active membership in the path organization;
3. the organization-local `members.manage` permission;
4. an exact configured `Origin` and a valid session-bound `X-CSRF-Token`.

The endpoint does not grant permissions. The existing default RBAC policy limits `members.manage` to owner/admin roles.

## Target and role validation

- Creation accepts only an existing, active, non-deleted user.
- Role changes require an active, non-deleted target user.
- The selected role must belong to the path organization.
- Duplicate creation returns HTTP 409.
- Missing/inactive/deleted users and roles from another organization return HTTP 404.
- Missing or foreign memberships return HTTP 404.
- A membership whose persisted role is inconsistent with its organization fails closed with HTTP 409.

These endpoints are not an invitation workflow: they do not create users, send email or provision credentials.

## Last active owner safeguard

A tenant must retain at least one active, non-deleted owner membership. Demoting or removing the final active owner returns HTTP 409.

Each membership mutation locks the organization row with `SELECT ... FOR UPDATE` before reading or changing memberships. The create path takes the same lock, so concurrent membership writes for a tenant are serialized on PostgreSQL. The safeguard counts only memberships whose user is active and not soft-deleted.

SQLite-based route tests validate the business rules but do not prove PostgreSQL row-lock behavior. The dedicated CI job `API PostgreSQL integration (membership concurrency)` now runs against an ephemeral PostgreSQL 16 service after applying all Alembic migrations.

The integration test synchronizes two authenticated owners immediately before the tenant-row lock, then submits concurrent role demotions. It requires exactly one HTTP 200, one HTTP 409, exactly one active owner remaining and exactly one `membership.role_changed` audit event. This verifies the row-lock safeguard under PostgreSQL contention; it does not claim that production RLS or a dedicated runtime database role has been configured.

## Audit and transaction

Successful mutations append one of:

- `membership.created`
- `membership.role_changed`
- `membership.deleted`

Each event records the authenticated actor, organization, membership target and non-secret identifiers/role names. Role changes include both previous and new role identifiers/names.

The membership write and audit row are flushed and committed in the same SQL transaction. If audit validation or insertion fails, the membership change is rolled back. No password, session token, cookie, CSRF value, IP address or user-agent is stored.

## Remaining limitations

- Invitations and email delivery are not implemented.
- Role catalogue administration remains a separate `roles.manage` capability.
- PostgreSQL RLS enforcement under a dedicated non-superuser runtime role remains a separate infrastructure/security task.
- The UI may expose only actions backed by these API endpoints; demo fixtures must not be represented as persisted memberships.

## Member listing contract

`GET /api/v1/organizations/{organization_id}/members` returns the stable `membership_id` and `role_id` alongside `user_id`, email, display name, role name and join timestamp. Clients must target mutations with `membership_id` and submit the selected role's `role_id`; role names are presentation labels, not identifiers. Both identifiers are scoped by the organization path and the server verifies tenant membership and `members.manage` before any mutation.

## Frontend integration

The Utilisateurs & rôles page uses the dedicated `apps/web/lib/membership-api.ts` client for the member listing and membership mutations. It submits role identifiers, not display names, includes the HttpOnly session cookie with `credentials: include`, and sends the session-bound `X-CSRF-Token` header on PATCH/DELETE. A missing CSRF token is rejected before a request is sent.

After a successful mutation, the member query is invalidated and reloaded from the API. The UI disables mutations until the current server session is resolved, prevents presenting self-removal as an available action, asks for confirmation before removal, and displays server 401/403/404/409 responses. These client-side affordances are not authorization controls: the API remains authoritative for `members.manage`, trusted Origin, CSRF and the last-active-owner invariant.
