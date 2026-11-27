# P1-A1 organization provisioning — API and frontend guide

This document describes the organization provisioning endpoints added by the
P1-A1 completion lot (branch `phase1/p1-a1-crud-complet`, base PR #51).
All routes live under `/api/v1`. Session cookie `eii_session` is HttpOnly and
sent with `credentials: "include"`; every state-changing route requires the
session CSRF token (`X-CSRF-Token` header, trusted Origin), except the
password-mode invitation acceptance, where the token itself authorizes the
call.

## Organizations

| Method | Route | Authorization |
|---|---|---|
| POST | `/api/v1/organizations` | Live session + CSRF (no membership yet) |
| GET | `/api/v1/organizations` | `organization.read` per organization |
| GET | `/api/v1/organizations/{id}` | `organization.read` |
| PATCH | `/api/v1/organizations/{id}` | `organization.manage` (owner only) |
| DELETE | `/api/v1/organizations/{id}` | `organization.manage` (owner only) |

- `POST` body: `{ "name": string, "slug": string }`. The slug is normalized
  (trimmed, lowercased) and must match `[a-z0-9]+(?:-[a-z0-9]+)*` (max 255).
  Duplicate slug → 409 (the database unique constraint is the final arbiter
  for concurrent creation). The creator becomes Organization Owner in the
  same transaction; the four system roles are created with the organization.
  Returns 201 with the organization. Audited as `organization.created`.
- `PATCH` body: `{ "name": string }`. The slug is immutable. Audited as
  `organization.updated` (with `previous_name`).
- `DELETE` is a soft delete (sets `deleted_at`, memberships and audit history
  are preserved). The audit event `organization.deleted` is recorded **before**
  marking the organization deleted, because the audit writer refuses actors
  of a deleted organization. There is no restore endpoint in this lot.

## Members and status

| Method | Route | Authorization |
|---|---|---|
| GET | `/api/v1/organizations/{id}/members` | `members.read` |
| GET | `/api/v1/organizations/{id}/members?include_inactive=true` | `members.read` |
| POST | `/api/v1/organizations/{id}/memberships` | `members.manage` |
| PATCH | `/api/v1/organizations/{id}/memberships/{mid}` | `members.manage` |
| DELETE | `/api/v1/organizations/{id}/memberships/{mid}` | `members.manage` |
| PATCH | `/api/v1/organizations/{id}/members/{mid}/status` | `members.manage` |

- The members list returns active members by default and now includes
  `is_active` per member. `include_inactive=true` also returns deactivated
  accounts (needed to reactivate them).
- `POST /memberships` adds an existing user by `user_id` + `role_id`
  (see [MEMBERSHIP_MUTATIONS.md](MEMBERSHIP_MUTATIONS.md)).
- `PATCH /members/{mid}/status` body: `{ "is_active": boolean }`.
  Deactivation is account-wide: the user can no longer log in anywhere.
  Refused with 409 for the actor's own account and for the last active
  Organization Owner. Idempotent (repeating the same state returns 200
  without a new audit event). Audited as `user.deactivated` /
  `user.reactivated`.

## Invitations (manual link, no email in PHASE 1)

| Method | Route | Authorization |
|---|---|---|
| POST | `/api/v1/organizations/{id}/invitations` | `members.manage` |
| GET | `/api/v1/organizations/{id}/invitations` | `members.read` |
| DELETE | `/api/v1/organizations/{id}/invitations/{invitation_id}` | `members.manage` |
| GET | `/api/v1/invitations/{token}` | Public (preview) |
| POST | `/api/v1/invitations/{token}/accept` | Public (token authorizes) |

- `POST /organizations/{id}/invitations` body:
  `{ "email": string, "role_id": uuid, "expires_in_days": 1–30 (default 7) }`.
  The role must belong to the organization (foreign role → 404). An existing
  member or a pending invitation for the same email → 409. Returns 201 with
  the invitation **plus `token` and `accept_path` — returned exactly once**.
  The token is never stored in clear (only its SHA-256 digest) and never
  appears in audit details or in the list response. Audited as
  `invitation.created`.
- `GET /organizations/{id}/invitations` returns the invitations with their
  computed status (`pending` / `accepted` / `revoked` / `expired`), never the
  token.
- `DELETE` revokes. Revoking an already revoked invitation is a no-op (204,
  no new audit event); revoking an accepted invitation is 409. Audited as
  `invitation.revoked`. Acceptance and revocation both take a PostgreSQL
  `SELECT ... FOR UPDATE` lock on the invitation row until commit/rollback:
  the first terminal transition wins, and the competing request observes the
  committed state (409 for revocation after acceptance, 404 for acceptance
  after revocation). The PostgreSQL integration job tests accept-vs-revoke and
  concurrent double-accept races.
- `GET /api/v1/invitations/{token}` (public preview) returns the organization
  name/slug, role name, invited email and expiry. Unknown, expired, revoked
  or accepted token → 404.
- `POST /api/v1/invitations/{token}/accept` (public) accepts in two modes:
  - **Authenticated:** a live session whose email matches the invited email;
    the CSRF check applies. This is the only path for MFA users.
  - **Password:** no session — `{ "password": string }` for an existing
    account, or `{ "display_name": string, "password": string }` to create
    the account. Wrong password → 401; session user is not the invitee →
    403; already a member → 409; invalid token → 404.
  - On success the response carries the organization and user identifiers
    and the role name. Acceptance does **not** create a session: the user
    must log in afterwards. Audited as `invitation.accepted` plus
    `membership.created`.

## Error contract

- 401: no live session, or invalid password on invitation acceptance.
- 403: missing permission, missing/invalid CSRF, or authenticated accept by a
  user who is not the invitee.
- 404: unknown organization/invitation/role, or invitation no longer valid
  (masked on purpose: an unknown token and an expired token look identical).
- 409: duplicate slug, duplicate pending invitation, already a member,
  self-deactivation, last active owner deactivation, revoking an accepted
  invitation.
- 422: invalid slug, name, email or expiry.

## Frontend

- `lib/organization-api.ts`: `createOrganization`, `updateOrganization`,
  `deleteOrganization` (with `organization-api.test.mjs`).
- `lib/invitation-api.ts`: `createOrganizationInvitation`,
  `listOrganizationInvitations`, `revokeOrganizationInvitation`,
  `previewInvitation`, `acceptInvitation` (with `invitation-api.test.mjs`).
- `lib/membership-api.ts`: `getOrganizationMembers(organizationId,
  includeInactive?)`, `createOrganizationMembership`, `updateMemberStatus`
  (tests in `membership-api.test.mjs`).
- Pages: `app/organisations/new` (creation form),
  `app/organisations` (inline rename, soft delete, guided empty state),
  `app/users` (status column + deactivate/reactivate, include-inactive
  toggle, add existing member, invitation creation/list/revocation with the
  accept link shown once and a copy button),
  `app/invitations/[token]` (public preview + double-mode acceptance).

## Out of scope (deferred)

- Custom roles (role catalogue administration).
- Organization restore endpoint.
- Standalone `/register` endpoint.
- `plan_id` / billing (PHASE 2+).
- Transactional email for invitations (decision D5).
