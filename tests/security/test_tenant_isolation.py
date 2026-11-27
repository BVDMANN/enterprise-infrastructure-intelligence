"""Legacy index for multi-tenant security test coverage.

Executable application-layer isolation tests now live in:
- apps/api/tests/test_organization_routes.py
- apps/api/tests/test_membership_mutation_routes.py
- apps/api/tests/test_audit_events.py

The isolated PostgreSQL RLS mechanics prototype lives in
apps/api/tests/test_postgres_rls_evaluation.py and runs only in its dedicated
ephemeral PostgreSQL CI job. It does not enable RLS in the application schema.

The skipped tests below are retained as historical placeholders only; they are
not security coverage and are not collected by the API CI job.
"""

import pytest


@pytest.mark.skip(
    reason="Historical placeholder; executable tenant read tests live in apps/api/tests."
)
def test_cross_tenant_resource_read_is_denied() -> None:
    """A user from org A must not read a resource of org B."""
    raise NotImplementedError


@pytest.mark.skip(
    reason="Historical placeholder; executable tenant write/audit tests live in apps/api/tests."
)
def test_cross_tenant_write_is_denied_and_audited() -> None:
    """A cross-tenant write must be rejected and recorded in the audit log."""
    raise NotImplementedError
