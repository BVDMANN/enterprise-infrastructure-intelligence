# Infrastructure metrics API — P1-A6.3

## Delivered in this lot

The Control Plane can persist and query individual metric samples attached to
an existing infrastructure asset.

- `POST /api/v1/organizations/{organization_id}/infrastructure/assets/{asset_id}/metrics`
  records one sample.
- `GET /api/v1/organizations/{organization_id}/infrastructure/assets/{asset_id}/metrics`
  returns newest samples first, with optional `metric_name`, `since`, `until` and
  bounded `limit` filters.

Writes require an authenticated server session, the
`infrastructure.manage` permission and the session-bound CSRF token. Reads
require `infrastructure.read`. The organization is resolved through the active
membership; the asset must belong to that organization.

## Data and integrity

Each row stores the organization, asset, normalized metric name, a decimal
value (up to 30 digits and 6 fractional places), optional unit, source timestamp
and server receive timestamp. The composite foreign key prevents attaching a
sample to an asset from another organization.

PostgreSQL enables and forces RLS on `infrastructure_metrics`, using the same
transaction-local organization/user context as the inventory and audit tables.
The table is append-only: UPDATE and DELETE are rejected by a trigger, and
TRUNCATE is rejected for both the runtime role (privilege boundary) and table
owner (statement-level trigger). The migration refuses to drop the table while
samples remain.

Metric names are lowercase identifiers such as `cpu.utilization`,
`memory.used_bytes`, `disk.used_bytes` or `network.rx_bytes`. Values are stored
as decimals; units are supplied explicitly (for example `%`, `bytes` or
`seconds`). Samples more than five minutes in the future are rejected.

## Audit trail

Each successful operator-facing metric POST appends an
`infrastructure.metric.recorded` event in the same database transaction as
the sample. The event identifies the organization, actor and asset and records
the normalized metric name, unit and `operator_api` ingestion source. It
deliberately excludes the metric value to avoid copying potentially sensitive
telemetry into the audit log. If the transaction fails, neither the sample nor
its audit event is committed.

This audit event describes the operator action that submitted the sample; it
does not claim to identify an infrastructure agent. A future agent ingestion
path must define its own volume-appropriate audit policy before it is enabled.

## Explicit limitations

This is an authenticated operator-facing ingestion API, not an agent protocol.
It does **not** yet authenticate infrastructure agents, poll Proxmox/Linux,
collect metrics automatically, schedule Celery ingestion, calculate alert
thresholds or provide time-series charts. No live telemetry is claimed until
the agent identity/authentication and collector pipeline are implemented and
connected to this API.
