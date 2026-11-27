# Infrastructure inventory UI — P1-A6.2

Status: implemented on \`phase1/p1-a6-infrastructure-ui\`; depends on the P1-A6.1 API branch and is not merged or deployed.

## Integrated behavior

The Infrastructure page reads the authenticated organization list and loads inventory records from:

\`GET /api/v1/organizations/{organization_id}/infrastructure/assets\`

The page supports:
- selecting an organization the current user can access;
- filtering by asset type and stored status;
- creating an asset with name, type, external identifier, provider and region;
- changing the stored status through PATCH;
- logical deletion through DELETE;
- loading, empty, session-expired, permission-denied, conflict and API-error states.

Mutations send the session-bound \`X-CSRF-Token\`; the browser includes the HttpOnly session cookie. The server remains authoritative for membership and RBAC checks.

## Data and security boundaries

The page displays only persisted API records. It no longer imports the infrastructure demo fixtures. The displayed counts are computed from the currently filtered API response and are not telemetry.

The UI does not collect or display CPU/memory metrics, agent heartbeats, connector sync, alert rules or incidents. The \`last_seen_at\` field is shown only as a caller-declared timestamp, never as proof of a live collector. Credentials must not be placed in inventory attributes.

## Validation

The branch adds Node contract tests for GET filters and tenant URL encoding, POST/PATCH/DELETE methods, CSRF headers, 204 responses and API error propagation. GitHub Actions is the authoritative validation environment; no local checkout or local test execution is claimed.
