# Authentication session audit events

This document describes the P1-A5 integration of local authentication with the tenant-scoped audit trail.

## Events emitted

The local email/password endpoints emit:

- `auth.session.created` after credentials are accepted and the opaque server-side session is created.
- `auth.session.revoked` after a valid logout request passes both the trusted-Origin and session-bound CSRF checks.

Each event uses:

- `target_type = auth_session`;
- `target_id = <server-side session UUID>` (never the bearer token);
- `details = {"method": "local_password"}`;
- the authenticated user as actor.

## Tenant scoping

A session event is written once for each active, non-deleted organization membership of the user. The event is stored only in that organization's audit stream. Organizations that have been soft-deleted are excluded.

A user without an organization membership can still authenticate and use the session endpoints, but no tenant-scoped audit event is created because there is no tenant to which the event can safely be attributed.

## Transaction and failure behavior

The audit writes share the SQLAlchemy transaction with session creation or revocation:

- a successful login commits the new session and its tenant audit events together;
- a successful logout commits the revocation and its tenant audit events together;
- if an audit write fails, the transaction is not committed, so a session is not created or revoked without its corresponding event.

Failed credentials, an untrusted Origin, and an invalid CSRF token do not produce success events.

## Data minimization

No password, password hash, session bearer token, CSRF token, cookie, IP address, user-agent or other credential material is copied into audit details. The session UUID is an internal target identifier, not an authentication credential.

## Current scope and limitations

This integration covers successful local-password session creation and revocation only. Failed-login/security telemetry, OIDC, MFA, invitations, membership mutations, role changes and infrastructure mutations are not yet instrumented. The audit endpoint and PostgreSQL append-only protections are described in [AUDIT_TRAIL.md](AUDIT_TRAIL.md); this work does not claim full business-event coverage or RLS isolation.
