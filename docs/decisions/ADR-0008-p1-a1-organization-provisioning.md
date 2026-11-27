# ADR-0008 — P1-A1 organization provisioning: creation, invitations, member status

- **Status:** Proposed — implementation on branch `phase1/p1-a1-crud-complet`, CI not yet run.
- **Date:** 2026-11-27.
- **Related:** ADR-0005, ADR-0006, PHASE1_PLAN.md P1-A1 (P1-03), P1-A2 sessions, P1-A3 RBAC, P1-A5 audit trail.
- **Note:** this ADR takes number 0008 now that it is implemented. The RLS lot
  proposal of 2026-11-27 had provisionally used ADR-0008; when that lot starts
  it must be renumbered (ADR-0009).

## Context

P1-A1 delivered the identity models and membership-scoped reads (PR #5/#8)
and the first protected GET routes (PR #18), but no organization could be
created through the product: `POST /organizations` did not exist, there was
no invitation workflow, no way to deactivate a user, and the bootstrap script
was broken since migration 0005 removed the `memberships.role` string column.
PHASE1_PLAN.md P1-A1 (P1-03) requires a complete module: functional CRUD APIs,
membership and status management, tests, frontend connected to the API, error
handling and documentation.

## Decisions

### 1. Organization creation: session + CSRF only

`POST /api/v1/organizations` requires a live session and the session CSRF
token, but no organization permission: the creator has no membership yet.
Creation is one transaction — organization, four system roles, owner
membership — and is audited as `organization.created`. The slug is validated
by the shared rule (lowercase, hyphen-separated) and is immutable afterwards;
`PATCH` renames only, `DELETE` soft-deletes only. `organization.manage` is
owner-only per the RBAC matrix, so no additional owner check is needed for
rename/delete.

### 2. Invitations by manual link (decision D5)

No transactional email in PHASE 1. The invitation token is returned exactly
once at creation with its accept path; the inviter copies the link manually.
Only the SHA-256 digest of the token is stored, and the token never appears
in audit details or in any later response. Invitations expire after 7 days
by default (1–30 days), are single-use, revocable (idempotent), and their
status (pending/accepted/revoked/expired) is computed from the timestamps.

### 3. Acceptance in two modes, authorized by the token

The tenant comes from the invitation, never from a value supplied by the
caller:

- **Authenticated mode:** the caller has a live session whose email matches
  the invited email; the CSRF check applies. This is the only path for MFA
  users (they have no usable password).
- **Password mode:** no session — the caller proves ownership of the invited
  email with its password (existing account) or creates the account with a
  display name and a password (new account). The password policy (12–128
  characters, Argon2id) is the existing one.

A wrong email in authenticated mode is 403; an invalid password is 401; an
unknown, expired, revoked or already accepted token is 404 (no leak).

### 4. Member status is account-wide

`PATCH /organizations/{id}/members/{membership_id}/status` deactivates or
reactivates the user's account (not a single membership): deactivation blocks
login everywhere. It requires `members.manage`, refuses self-deactivation
(409) and refuses deactivating the last active Organization Owner (409, same
guard as role change and membership removal). The change is idempotent and
audited as `user.deactivated` / `user.reactivated`.

### 5. No custom roles in this lot

The four system roles cover the MVP. The role catalogue administration is
deferred; `plan_id` (billing, PHASE 2+) is out of scope; no standalone
`/register` endpoint is added (account creation happens through invitation
acceptance, which is A1 territory, not a parallel A2 registration flow).

### 6. Bootstrap repair

`scripts/bootstrap_admin.py` is fixed to the post-0005 model: it creates the
system roles via `create_default_roles_for_organization` and assigns the
owner membership by `role_id` (the `role="owner"` string write was broken).
It reuses the shared slug validation. No provisioning path other than the
service and the bootstrap script may create an organization.

## Consequences

- New audit event types: `organization.created`, `organization.updated`,
  `organization.deleted`, `user.deactivated`, `user.reactivated`,
  `invitation.created`, `invitation.revoked`, `invitation.accepted`.
- New migration `0007_organization_invitations` (head); the migration chain
  stays linear (0001 → 0007).
- Frontend: organization creation page, inline rename and soft delete on the
  organizations page, member status column with deactivate/reactivate, add
  existing member by user UUID, invitation creation/list/revocation with the
  accept link shown once, public accept page (`/invitations/[token]`).
- The RLS lot (future ADR-0009) is unaffected: no table gains a policy here,
  and the invitation token digest is not a credential.
