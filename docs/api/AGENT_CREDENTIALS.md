# Infrastructure agent credentials — P1-A7.1

## Delivered in this lot

An organization owner/admin with `infrastructure.manage` can issue a
credential for one existing infrastructure asset:

`POST /api/v1/organizations/{organization_id}/infrastructure/assets/{asset_id}/agents`

Request:

```json
{
  "name": "proxmox-node-01",
  "expires_in_days": 90
}
```

The expiry is bounded to 1–365 days. The default is 90 days. The response
contains the plaintext `eii_agent_...` bearer token exactly once and sets
`Cache-Control: no-store` plus `Pragma: no-cache`. The API
stores only its SHA-256 digest and a short display prefix; the raw token is
not stored, returned by list endpoints, written to audit details or logged.

Authorized members with `infrastructure.read` can list credential metadata:

`GET /api/v1/organizations/{organization_id}/infrastructure/assets/{asset_id}/agents`

Owners/admins with `infrastructure.manage` can revoke a credential:

`DELETE /api/v1/organizations/{organization_id}/infrastructure/assets/{asset_id}/agents/{credential_id}`

Revocation is idempotent. A revoked credential cannot be reactivated or
modified to point to another organization/asset. The database trigger makes
the credential identity fields immutable and the migration refuses to drop
the table while credential records remain.

## Tenant and token lookup controls

- Every credential is bound to one organization and one asset by a composite
  foreign key.
- Management reads/writes require an authenticated user session, the
  organization-scoped RBAC permission and CSRF protection on mutations.
- PostgreSQL RLS permits member management only in the active organization.
- Agent token lookup uses the transaction-local
  `app.current_agent_token_hash` setting. Its SELECT policy exposes only the
  non-expired, non-revoked row whose digest matches that setting.
- After token lookup, the service establishes the credential's organization
  and enrolling user as the delegated tenant context, then verifies that the
  user, membership, organization and asset are still active.
- Deactivating the enrolling user, deleting their membership, deleting the
  organization or soft-deleting the asset makes the credential unusable.
- The runtime role has no DELETE RLS policy for this table. TRUNCATE is
  blocked by a statement-level trigger; identity-field updates are blocked
  by a row trigger. Only the one-way transition from active to revoked is
  allowed.

The token hash is high-entropy lookup material, not a password hash. The
token is generated with 32 bytes of cryptographic randomness before URL-safe
encoding. A SHA-256 digest is appropriate for this random bearer token; it
would not be appropriate for human-chosen passwords.

## Explicit limitations

This lot implements credential issuance, metadata listing, revocation and an
internal token-verification service. It does **not** yet expose an agent-facing
heartbeat or metrics-ingestion endpoint, mTLS, automated enrollment,
rotation without re-enrollment, rate limiting for agent authentication,
Proxmox/Linux collection, Celery ingestion or alerting. No live agent or
automatic telemetry is claimed.

The delegated principal is the active user who enrolled the agent. This is a
conservative first step: deactivating that user or revoking their membership
also disables the agent. A future service-principal model may decouple agent
lifecycle from an individual employee, but it must preserve organization and
asset scoping and a verifiable revocation path.

For production rollout, the one-time token must be delivered to the host via
an approved secret-management channel and never pasted into tickets, source
control or logs. mTLS/device identity and a dedicated agent runtime boundary
remain separate acceptance criteria.
