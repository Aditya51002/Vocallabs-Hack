"""Authentication, ownership, and lightweight abuse controls."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Dict, Optional
from uuid import UUID

from fastapi import HTTPException, Request, WebSocket, status

from config import settings
from core.auth import decode_access_token

SESSION_META_KEY = "session:{session_id}:meta"


@dataclass(frozen=True)
class AuthContext:
    """Identity attached to a request after JWT or API-key authentication."""

    user_id: str
    authenticated: bool


def configured_api_keys() -> Dict[str, str]:
    """Parse RESEARCHSWARM_API_KEYS into {key: user_id}."""

    raw = settings.api_keys.get_secret_value().strip()
    if not raw:
        return {}

    parsed: Dict[str, str] = {}
    for index, item in enumerate(raw.split(","), start=1):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            user_id, key = item.split(":", 1)
            user_id = user_id.strip() or f"user-{index}"
            key = key.strip()
        else:
            user_id = "default"
            key = item
        if key:
            parsed[key] = user_id
    return parsed


def auth_enabled() -> bool:
    """Return True since authentication is always active."""

    return True


async def require_auth(request: Request) -> AuthContext:
    """Authenticate HTTP requests via JWT Bearer token or static API keys."""

    auth_header = request.headers.get("authorization")
    token = _extract_bearer(auth_header)

    if token:
        payload = decode_access_token(token)
        if payload:
            return AuthContext(user_id=payload["sub"], authenticated=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    keys = configured_api_keys()
    if keys:
        supplied = _extract_http_key(request)
        user_id = _match_key(supplied, keys)
        if user_id:
            return AuthContext(user_id=user_id, authenticated=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API key required",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


async def authenticate_websocket(websocket: WebSocket) -> AuthContext:
    """Authenticate WebSocket clients before accepting the connection."""

    # Extract token from query params or header
    token = (
        websocket.query_params.get("token")
        or _extract_bearer(websocket.headers.get("authorization"))
    )

    if token:
        payload = decode_access_token(token)
        if payload:
            return AuthContext(user_id=payload["sub"], authenticated=True)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise PermissionError("Invalid or expired token")

    keys = configured_api_keys()
    if keys:
        supplied = (
            websocket.query_params.get("api_key")
            or websocket.headers.get("x-api-key")
        )
        user_id = _match_key(supplied, keys)
        if user_id:
            return AuthContext(user_id=user_id, authenticated=True)

    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    raise PermissionError("Authentication required")


async def ensure_session_access(
    request: Request, session_id: str, auth: AuthContext
) -> None:
    """Ensure the authenticated user owns the requested session."""

    meta = await request.app.state.redis.hgetall(
        SESSION_META_KEY.format(session_id=session_id)
    )
    if not meta:
        raise HTTPException(status_code=404, detail="Session not found")

    # Handle Redis returning bytes or strings
    owner_id = meta.get(b"owner_id", meta.get("owner_id"))
    if isinstance(owner_id, bytes):
        owner_id = owner_id.decode("utf-8")

    if owner_id != auth.user_id:
        raise HTTPException(status_code=404, detail="Session not found")


async def ensure_websocket_session_access(
    websocket: WebSocket, session_id: str, auth: AuthContext
) -> bool:
    """Return True if the WebSocket identity can read the session."""

    meta = await websocket.app.state.redis.hgetall(
        SESSION_META_KEY.format(session_id=session_id)
    )
    owner_id = meta.get(b"owner_id", meta.get("owner_id"))
    if isinstance(owner_id, bytes):
        owner_id = owner_id.decode("utf-8")

    if owner_id == auth.user_id:
        return True

    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return False


async def enforce_session_rate_limit(request: Request, auth: AuthContext) -> None:
    """Apply a fixed-window rate limit for session creation."""

    limit = settings.session_rate_limit
    window = settings.session_rate_window_seconds
    if limit <= 0 or window <= 0:
        return

    client_host = request.client.host if request.client else "unknown"
    identity = auth.user_id if auth.authenticated else client_host
    key = f"rate:create_session:{identity}"
    count = await request.app.state.redis.incr(key)
    if count == 1:
        await request.app.state.redis.expire(key, window)
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sessions started; try again shortly",
        )


def _extract_http_key(request: Request) -> Optional[str]:
    return (
        request.headers.get("x-api-key")
        or request.query_params.get("api_key")
    )


def _extract_bearer(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    prefix = "bearer "
    if value.lower().startswith(prefix):
        return value[len(prefix) :].strip()
    return None


def _match_key(supplied: Optional[str], keys: Dict[str, str]) -> Optional[str]:
    matched_user_id: Optional[str] = None
    for key, user_id in keys.items():
        supplied_value = supplied if supplied is not None else "\0" * len(key)
        if hmac.compare_digest(supplied_value, key):
            matched_user_id = user_id
    return matched_user_id


def normalize_session_id(session_id: str | UUID) -> str:
    """Return a canonical UUID session id or raise a 404-safe error."""

    try:
        return str(session_id if isinstance(session_id, UUID) else UUID(str(session_id)))
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Session not found")
