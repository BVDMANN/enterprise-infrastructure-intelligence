"""Public invitation preview and acceptance (P1-A1 completion).

These two endpoints are intentionally public: the invitation token
is the authorization. The tenant comes from the invitation itself,
never from a value supplied by the caller, and the token is never
returned or logged.

Acceptance has two modes:
- authenticated: the caller has a live session whose email matches
  the invitation email (CSRF required; the only path for MFA users);
- password: no session — the caller proves ownership of the invited
  email with its password (existing account) or creates the account
  with a display name and a password (new account).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.authorization import require_session_csrf
from app.core.session_constants import SESSION_COOKIE
from app.db.session import get_db
from app.models.identity import Invitation, Organization, User
from app.models.rbac import Role
from app.services.invitations import (
    InvitationConflictError,
    InvitationForbiddenError,
    InvitationNotFoundError,
    InvitationUnauthorizedError,
    InvitationValidationError,
    accept_invitation,
)
from app.services.sessions import get_active_session

router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])


class InvitationPreviewResponse(BaseModel):
    """Public preview of a pending invitation (no token, no user data)."""

    organization_name: str
    organization_slug: str
    role_name: str
    email: str
    expires_at: str


class InvitationAcceptRequest(BaseModel):
    """Password mode: display name (new account only) and password."""

    display_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, max_length=128)


class InvitationAcceptResponse(BaseModel):
    """Acceptance result: the organization the user just joined."""

    organization_id: str
    organization_name: str
    organization_slug: str
    user_id: str
    email: str
    role_name: str


def _find_pending_invitation(db: Session, *, token: str) -> Invitation | None:
    """Locate a pending invitation by token digest (404 otherwise)."""
    from app.services.invitations import hash_invitation_token, invitation_status

    invitation = db.scalar(
        select(Invitation).where(Invitation.token_hash == hash_invitation_token(token))
    )
    if invitation is None:
        return None
    if invitation_status(invitation) != "pending":
        return None
    organization = db.get(Organization, invitation.organization_id)
    if organization is None or organization.deleted_at is not None:
        return None
    return invitation


@router.get("/{token}", response_model=InvitationPreviewResponse)
def preview_invitation(
    token: str,
    db: Session = Depends(get_db),
) -> InvitationPreviewResponse:
    """Preview a pending invitation (organization, role, email, expiry)."""
    invitation = _find_pending_invitation(db, token=token)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found or no longer valid",
        )
    organization = db.get(Organization, invitation.organization_id)
    role = db.scalar(
        select(Role).where(
            Role.id == invitation.role_id,
            Role.organization_id == organization.id,
        )
    )
    return InvitationPreviewResponse(
        organization_name=organization.name,
        organization_slug=organization.slug,
        role_name=role.name if role is not None else "unknown",
        email=invitation.email,
        expires_at=invitation.expires_at.isoformat(),
    )


@router.post("/{token}/accept", response_model=InvitationAcceptResponse)
def accept_invitation_endpoint(
    token: str,
    payload: InvitationAcceptRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> InvitationAcceptResponse:
    """Accept a pending invitation, authenticated or by password.

    With a live session, the session user must be the invitee and the
    CSRF check applies. Without a session, the password proves
    ownership of the invited email (existing account) or creates the
    account (new account, display name required).
    """
    # A session, when present, is resolved without raising: an
    # anonymous caller falls through to password mode. get_active_session
    # already requires the session user to be active and not deleted.
    session_user: User | None = None
    active_session = get_active_session(db, request.cookies.get(SESSION_COOKIE))
    if active_session is not None:
        # A session is present: it must belong to the invitee and the
        # CSRF check applies (same rule as every state-changing route).
        require_session_csrf(request, db)
        session_user = db.get(User, active_session.user_id)
        if session_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

    try:
        invitation, _membership, organization, user = accept_invitation(
            db,
            token=token,
            display_name=payload.display_name,
            password=payload.password,
            session_user=session_user,
        )
        db.commit()
    except InvitationNotFoundError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except InvitationForbiddenError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except InvitationUnauthorizedError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    except InvitationConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except InvitationValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    role = db.scalar(
        select(Role).where(
            Role.id == invitation.role_id,
            Role.organization_id == organization.id,
        )
    )
    return InvitationAcceptResponse(
        organization_id=str(organization.id),
        organization_name=organization.name,
        organization_slug=organization.slug,
        user_id=str(user.id),
        email=user.email,
        role_name=role.name if role is not None else "unknown",
    )
