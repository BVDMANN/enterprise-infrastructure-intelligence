"""Transaction-local tenant context for PostgreSQL RLS-protected tables."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def set_current_organization(
    db: Session,
    organization_id: UUID,
    user_id: UUID | None = None,
) -> None:
    """Set tenant/user context only for the current transaction.

    SQLite tests remain unchanged. On PostgreSQL, the policies require both
    values and independently verify that the user has an active membership
    in the selected organization. Omitting user_id never clears an existing
    transaction-local user context.
    """
    if db.get_bind().dialect.name != "postgresql":
        return

    db.execute(
        text(
            "SELECT set_config("
            "'app.current_organization_id', :organization_id, true)"
        ),
        {"organization_id": str(organization_id)},
    )
    if user_id is not None:
        db.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": str(user_id)},
        )
