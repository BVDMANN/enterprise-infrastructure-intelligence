"""Authenticated-session and organization-scoped RBAC dependencies."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.session_constants import SESSION_COOKIE
from app.db.session import get_db
from app.db.tenant_context import set_current_organization
from app.models.identity import Organization, User
from app.services.identity import get_organization_for_user
from app.services.rbac import PermissionDenied, require_permission
from app.services.sessions import get_active_session, verify_csrf_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Resolve the active user exclusively from the opaque server session."""
    session = get_active_session(db, request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_session_csrf(
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    """Require a trusted Origin and CSRF token bound to the active session."""
    origin = request.headers.get("origin")
    if not origin or origin not in settings.cors_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted origin",
        )

    token = request.cookies.get(SESSION_COOKIE)
    csrf_token = request.headers.get("x-csrf-token")
    if not verify_csrf_token(db, token, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


def require_organization_permission(
    permission_name: str,
) -> Callable[..., Organization]:
    """Build a dependency that hides non-member tenants and fails closed on RBAC."""

    def dependency(
        organization_id: UUID,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> Organization:
        organization = get_organization_for_user(
            db,
            current_user.id,
            organization_id,
        )
        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found",
            )

        try:
            require_permission(
                db,
                current_user.id,
                organization.id,
                permission_name,
            )
        except PermissionDenied as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient organization permission",
            ) from exc

        set_current_organization(db, organization.id)
        return organization

    return dependency
