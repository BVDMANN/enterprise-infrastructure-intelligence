# Tenant membership creation API

This P1-A5.2 endpoint is the first business mutation connected to the append-only audit writer.

## Endpoint

`POST /api/v1/organizations/{organization_id}/memberships`

Request body:

```json
{
  "user_id": "existing-user-uuid",
  "role_id": "role-uuid-from-the-same-organization"
}
```

The endpoint returns HTTP 201 with the new membership UUID, user UUID, role UUID and creation timestamp.

## Authorization and CSRF

The caller must:

1. have a live server-side session;
2. be an active member of the requested organization;
3. hold the existing organization-local `members.manage` permission;
4. send an exact configured `Origin` and a valid session-bound `X-CSRF-Token`.

No permission is granted by this endpoint. The default RBAC policy keeps `members.manage` limited to the existing owner/admin roles.

## Target validation

- Only an already-existing, active, non-deleted user can be added.
- The selected role must belong to the requested organization.
- A user already in the organization receives HTTP 409.
- A missing/inactive/deleted user or a role from another organization receives HTTP 404.
- The composite membership foreign key remains the database-level tenant/role constraint.

This is **not** an invitation workflow: it does not create users, send email, provision credentials, change roles, or remove memberships.

## Audit and transaction

On success, the route appends `membership.created` with:

- actor: the authenticated caller;
- tenant: the authorized organization;
- target: the newly created membership UUID;
- details: target user UUID, organization-local role UUID and role name.

The membership insert and audit row are flushed and committed in the same SQL transaction. If audit validation or insertion fails, the transaction is not committed. No password, token, cookie, CSRF value, IP or user-agent is stored.

## Current limitations

The endpoint supports creation only. Membership updates/removals, invitations, role changes, last-owner safeguards, RLS enforcement and UI integration remain separate work. The existing members list remains the read API; the frontend is not yet wired to this mutation.
