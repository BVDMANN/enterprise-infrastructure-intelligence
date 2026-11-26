"""Local email/password authentication endpoints (P1-A2.2)."""

from datetime import timedelta
from hashlib import sha256
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.identity import User
from app.services.passwords import authenticate_user
from app.services.sessions import (
    create_session,
    get_active_session,
    revoke_session,
    verify_csrf_token,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
SESSION_COOKIE = "eii_session"
SESSION_TTL = timedelta(hours=8)


class LoginRequest(BaseModel):
    """Credentials accepted by the local login endpoint."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Safe public identity fields; never includes credential material."""

    id: UUID
    email: str
    display_name: str


class LoginResponse(BaseModel):
    """Login result; the session token is only sent in an HttpOnly cookie."""

    user: UserResponse
    csrf_token: str


def _require_trusted_origin(request: Request) -> None:
    """Reject browser mutations without an exact configured Origin."""
    origin = request.headers.get("origin")
    if not origin or origin not in settings.cors_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Untrusted origin"
        )


def _enforce_login_rate_limit(request: Request, email: str) -> None:
    """Apply distributed IP and account limits; fail closed if Redis is unavailable."""
    client_ip = request.client.host if request.client else "unknown"
    ip_key = "eii:auth:login:ip:" + sha256(client_ip.encode()).hexdigest()
    email_key = (
        "eii:auth:login:email:" + sha256(email.strip().lower().encode()).hexdigest()
    )
    script = (
        "local ip_count = redis.call('INCR', KEYS[1]); "
        "if ip_count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[3]); end; "
        "local email_count = redis.call('INCR', KEYS[2]); "
        "if email_count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[3]); end; "
        "if ip_count > tonumber(ARGV[2]) or email_count > tonumber(ARGV[1]) "
        "then return 1 else return 0 end"
    )
    try:
        redis = Redis.from_url(
            settings.redis_url, socket_connect_timeout=1, socket_timeout=1
        )
        try:
            limited = redis.eval(script, 2, ip_key, email_key, 5, 20, 300)
        finally:
            redis.close()
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        ) from exc
    if limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts; try again later",
            headers={"Retry-After": "300"},
        )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=settings.api_env != "development",
        samesite="lax",
        path="/api/v1",
    )


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """Authenticate a local user and issue an opaque server-side session."""
    _require_trusted_origin(request)
    _enforce_login_rate_limit(request, payload.email)
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Cookie"},
        )
    credentials = create_session(db, user.id, ttl=SESSION_TTL)
    db.commit()
    _set_session_cookie(response, credentials.session_token)
    return LoginResponse(
        user=UserResponse(id=user.id, email=user.email, display_name=user.display_name),
        csrf_token=credentials.csrf_token,
    )


@router.get("/me", response_model=UserResponse)
def current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Return the identity attached to the current live session."""
    token = request.cookies.get(SESSION_COOKIE)
    session = get_active_session(db, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> Response:
    """Require Origin and session-bound CSRF before revoking the session."""
    _require_trusted_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    csrf_token = request.headers.get("x-csrf-token")
    if not verify_csrf_token(db, token, csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token"
        )
    revoke_session(db, token)
    db.commit()
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/api/v1",
        secure=settings.api_env != "development",
        httponly=True,
        samesite="lax",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
