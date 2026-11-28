# Infrastructure metrics API — P1-A6.3 / P1-A7.2

## Delivered functionality

The Control Plane persists and queries metric samples attached to an existing
infrastructure asset.

- `POST /api/v1/organizations/{organization_id}/infrastructure/assets/{asset_id}/metrics`
  records one operator-submitted sample.
- `GET /api/v1/organizations/{organization_id}/infrastructure/assets/{asset_id}/metrics`
  returns newest samples first, with optional `metric_name`, `since`, `until`
  and bounded `limit` filters.
- Agent-facing ingestion is documented separately in
  [AGENT_INGESTION.md](AGENT_INGESTION.md).

Operator writes require an authenticated server session, the
`infrastructure.manage` permission and the session-bound CSRF token. Reads
require `infrastructure.read`. The organization is resolved through the active
membership; the asset must belong to that organization.

## Data and integrity

Each row stores the organization, asset, normalized metric name, a decimal
value (up to 30 digits and 6 fractional places), optional unit, ingestion
source, source timestamp and server receive timestamp. The composite foreign
key prevents attaching a sample to an asset from another organization.

The `ingestion_source` column is constrained to `operator_api` or
`agent_api`. Existing rows are migrated as `operator_api`; the database
default preserves the same behavior for older clients that do not supply a
source. The API does not allow a browser/operator payload to choose this field.

PostgreSQL enables and forces RLS on `infrastructure_metrics`, using the same
transaction-local organization/user context as the inventory and audit tables.
The table is append-only: UPDATE and DELETE are rejected by a trigger, and
TRUNCATE is rejected for both the runtime role (privilege boundary) and table
owner (statement-level trigger). The migration refuses to drop the table while
samples remain. The source migration also refuses to remove provenance while
agent-ingested rows exist.

Metric names are lowercase identifiers such as `cpu.utilization`,
`memory.used_bytes`, `disk.used_bytes` or `network.rx_bytes`. Values are
stored as decimals; units are supplied explicitly (for example `%`, `bytes`
or `seconds`). Samples more than five minutes in the future are rejected.

## Audit trail

Each successful operator-facing metric POST appends an
`infrastructure.metric.recorded` event in the same database transaction as
the sample. The event identifies the organization, actor and asset and records
the normalized metric name, unit and `operator_api` ingestion source. It
deliberately excludes the metric value to avoid copying potentially sensitive
telemetry into the audit log.

Each successful agent batch appends one
`infrastructure.agent.metrics.ingested` event in the same transaction as all
samples in that batch. Its details identify `actor_type=infrastructure_agent`, the credential
record ID, sample count and `agent_api` source; they exclude metric values,
token plaintext and token digest. The required `actor_user_id` is the active
user who enrolled the credential, while `actor_type` explicitly identifies
the delegated infrastructure agent as the ingestion principal. Heartbeats do
not create audit rows because they may be high frequency; they update only
`last_seen_at`. If a batch or its audit event fails, the whole transaction is
rolled back.

## Explicit limitations

The operator API and the first bearer-authenticated agent ingestion endpoints
are real and persisted. This does **not** yet provide a packaged Linux or
Proxmox collector, automatic polling, mTLS, rate limiting, batch idempotency,
Celery scheduling, alert thresholds or time-series dashboards. Asset status
is not changed to `healthy` merely because an agent heartbeat succeeds.
No live telemetry is claimed until a collector is installed and configured to
send measurements.
