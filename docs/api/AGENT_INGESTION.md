# Infrastructure agent ingestion — P1-A7.2

## Endpoints

The P1-A7.1 credential is accepted as an HTTP bearer token:

- `POST /api/v1/agent/heartbeat` updates the bound asset's `last_seen_at`.
- `POST /api/v1/agent/metrics` accepts and persists a batch of 1–100 metric
  samples.

Example request:

```http
POST /api/v1/agent/metrics
Authorization: Bearer <one-time-agent-token>
Content-Type: application/json
```

```json
{
  "samples": [
    {
      "metric_name": "cpu.utilization",
      "metric_value": "12.5",
      "unit": "%"
    },
    {
      "metric_name": "memory.used_bytes",
      "metric_value": "1073741824",
      "unit": "bytes"
    }
  ]
}
```

The credential, not the request body or URL, determines the organization and
asset. Clients cannot submit an organization ID, asset ID, ingestion source,
token hash or actor ID. Unknown fields are rejected. Each sample uses the
existing metric contract: lowercase normalized metric name, finite decimal
value, optional normalized unit and timezone-aware source timestamp (default
is server-side request time). A source timestamp more than five minutes in
the future is rejected.

Agent requests use bearer authentication only; they do not require a browser
session cookie, CSRF token or trusted browser Origin. Invalid, expired, revoked,
deactivated-user, removed-membership or deleted-asset credentials receive the
same generic 401 response. Successful responses are non-cacheable. Send tokens
only over HTTPS and keep them in the host's secret store; never put them in a
URL or log them.

## Persistence and tenant boundary

Every accepted sample is stored in the existing append-only
`infrastructure_metrics` table with `ingestion_source=agent_api`. Operator
submissions retain `operator_api`. The server sets the organization and asset
from the authenticated credential and updates the asset's `last_seen_at` in
the same transaction. It does not automatically mark the asset healthy.

A batch is all-or-nothing. The endpoint validates the entire payload before
writing, inserts all samples and one audit event in a single SQL transaction,
and returns only the asset ID, accepted sample count and receive timestamp.
The audit event is `infrastructure.agent.metrics.ingested`; it identifies
`actor_type=infrastructure_agent`, the credential record ID and sample count,
but contains no metric values, plaintext token or token digest. Its
`actor_user_id` is the active user who enrolled the credential, not a claim
that a human submitted the batch. Heartbeats update `last_seen_at` without
creating a high-volume audit event.

The runtime PostgreSQL role is subject to the existing forced RLS policies on
agent credentials, assets, metrics and audit events. The credential service
must resolve a live token and revalidate the enrolling user, active membership,
organization and asset before the route writes. A PostgreSQL integration test
runs the service with `eii_runtime` and verifies that a token for organization
A cannot insert a metric for organization B.

## Operational limitations — not implemented in this lot

- No packaged agent binary, Linux systemd unit, Proxmox integration or
  automatic collector/poller.
- No mTLS, rate limiting, credential rotation protocol or batch idempotency
  key. Retried batches can therefore create duplicate samples.
- No queue/Celery ingestion; the bounded batch is persisted synchronously.
- No alert engine or automatic asset-status transition.
- The application still uses transaction-local PostgreSQL custom GUC values
  for RLS context. As documented in P1-A7.1, these are not a defense against
  arbitrary SQL execution under a compromised runtime role.

The endpoints are an authenticated ingestion contract, not proof that any
machine is already sending live telemetry.
