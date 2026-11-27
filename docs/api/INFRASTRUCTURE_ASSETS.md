# Infrastructure asset inventory API — P1-A6.1

Status: implemented in the P1-A6.1 branch; not yet merged or deployed.

## Scope

This increment provides an organization-scoped inventory API. It does not
claim to collect telemetry, execute connector syncs, evaluate alert rules, or
provide live health metrics. The last_seen_at field is metadata supplied by
an authorized caller; no collector currently updates it automatically.

## Routes

All routes are rooted at
/api/v1/organizations/{organization_id}/infrastructure/assets.

| Method | Route | Permission | Purpose |
|---|---|---|---|
| GET | collection | infrastructure.read | List non-deleted assets |
| POST | collection | infrastructure.manage | Create an asset |
| GET | /{asset_id} | infrastructure.read | Read one asset |
| PATCH | /{asset_id} | infrastructure.manage | Update supplied fields |
| DELETE | /{asset_id} | infrastructure.manage | Soft-delete an asset |

Writes require the active server-side session, a trusted Origin, and the
session-bound X-CSRF-Token. Reads and writes first resolve the requested
organization through the authenticated user's active membership and then
check the named organization permission. A resource in another organization
is returned as 404, not disclosed.

The collection supports asset_type, status, and limit filters.
limit defaults to 50 and is bounded from 1 to 100. Results are ordered by
most recently updated, then by id.

## Data contract

- asset_type: server, virtual_machine, container, cluster, database, network,
  storage, cloud_resource, service, or other.
- status: unknown, healthy, degraded, unhealthy, or offline.
- external_id is optional and unique within an organization when present.
  Soft deletion does not release this identifier; reuse requires a separately
  reviewed retention/purge policy.
- attributes is a JSON object capped at 16 KiB. Nested keys containing
  password, secret, token, authorization, cookie, CSRF, API-key, or private-key
  markers are rejected. Do not store credentials in this field.
- last_seen_at must be timezone-aware. It is not proof of a live collector.

Every create/update/delete appends a tenant-attributed audit event in the same
database transaction. Update audit details contain changed field names only,
not field values.

## Persistence and security boundaries

Migration 0007_infrastructure_assets creates an organization foreign key,
organization-scoped external-id uniqueness, allowed-value checks, and indexes
for organization/status/type/update-time lookups. Downgrade refuses to drop
the table while any inventory row remains.

The API enforces tenant scope through session + membership + RBAC checks and
tenant-filtered queries. This migration does not enable PostgreSQL RLS on the
table. RLS remains a separate security milestone and must not be inferred
from application-layer scoping.

## Not implemented in this increment

- Connector identity, mTLS, discovery, sync runs, or ingestion endpoints.
- Metric samples, time-series retention, alert rules, alert lifecycle, or
  incident management.
- Automatic status transitions or health calculations.
- Frontend integration; the Infrastructure page remains explicitly DEMO until
  a separate UI PR consumes these endpoints.
