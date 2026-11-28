"""Transaction-local tenant and agent lookup context for PostgreSQL RLS."""

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


def set_current_agent_token_hash(db: Session, token_hash: str | None) -> None:
    """Expose only one digest to the transaction-local agent lookup RLS policy."""
    if token_hash is not None and (
        len(token_hash) != 64
        or any(character not in "0123456789abcdef" for character in token_hash)
    ):
        raise ValueError("Agent token hash must be a lowercase SHA-256 digest")

    if db.get_bind().dialect.name != "postgresql":
        return

    db.execute(
        text(
            "SELECT set_config("
            "'app.current_agent_token_hash', :token_hash, true)"
        ),
        {"token_hash": token_hash or ""},
    )
