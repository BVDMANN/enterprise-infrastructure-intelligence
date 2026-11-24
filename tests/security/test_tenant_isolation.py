"""Security tests — multi-tenant isolation (PHASE 0 skeleton).

The real isolation tests arrive in PHASE 1 with the first models and a
test database (see docs/architecture/DATABASE_DESIGN.md §6 and
docs/security/SECURITY_ARCHITECTURE.md §4).

Planned cases:
- user from organization A cannot read resources of organization B (404/403)
- user from organization A cannot list users of organization B
- cross-tenant writes are rejected (403) and audited
- RLS evaluation (ADR-0005) is decided before these tests are finalized
"""

import pytest


@pytest.mark.skip(
    reason="PHASE 1: requires models, test database and authenticated fixtures."
)
def test_cross_tenant_resource_read_is_denied() -> None:
    """A user from org A must not read a resource of org B."""
    raise NotImplementedError


@pytest.mark.skip(
    reason="PHASE 1: requires models, test database and authenticated fixtures."
)
def test_cross_tenant_write_is_denied_and_audited() -> None:
    """A cross-tenant write must be rejected and recorded in the audit log."""
    raise NotImplementedError
