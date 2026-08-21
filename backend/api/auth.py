"""FastAPI authentication router for signup, login, and user profile."""

from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from config import settings
from core.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    decode_access_token,
    get_user_by_email,
)
from core.security import require_auth, AuthContext

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: str = Field(..., description="User email address")
    name: str = Field(..., description="Full name")
    password: str = Field(..., min_length=8, description="Password (at least 8 chars)")


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    id: str
    email: str
    name: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


async def _enforce_auth_rate_limit(request: Request) -> None:
    """Enforce rate limits on signup/login to prevent brute-force attacks."""

    redis = request.app.state.redis
    client_ip = request.client.host if request.client else "unknown"
    now = int(time.time())
    window_start = now - (now % settings.auth_rate_window_seconds)
    key = f"rate:auth:{client_ip}:{window_start}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, settings.auth_rate_window_seconds)

    if current > settings.auth_rate_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
        )


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_enforce_auth_rate_limit)],
)
async def signup(body: SignupRequest, request: Request) -> AuthResponse:
    """Register a new user account."""

    redis = request.app.state.redis
    try:
        user = await create_user(
            redis,
            email=body.email,
            name=body.name,
            password=body.password,
        )
    except ValueError as exc:
        err = str(exc)
        if err == "email_taken":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already registered.",
            )
        if err == "invalid_email":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Please provide a valid email address.",
            )
        if err == "invalid_name":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Please provide a valid name.",
            )
        if err == "password_too_short":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password must be at least 8 characters long.",
            )
        if err == "password_too_long":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Password exceeds maximum length limit.",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration failed.",
        )

    token = create_access_token(user)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(id=user["id"], email=user["email"], name=user["name"]),
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_enforce_auth_rate_limit)],
)
async def login(body: LoginRequest, request: Request) -> AuthResponse:
    """Authenticate an existing user and return a JWT access token."""

    redis = request.app.state.redis
    user = await authenticate_user(
        redis,
        email=body.email,
        password=body.password,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(user)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(id=user["id"], email=user["email"], name=user["name"]),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_current_user(
    request: Request,
    auth: AuthContext = Depends(require_auth),
) -> UserResponse:
    """Get the profile of the currently authenticated user."""

    if not auth.authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    # Decode JWT Bearer token directly or fetch profile
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        payload = decode_access_token(token)
        if payload:
            return UserResponse(
                id=payload["sub"],
                email=payload.get("email", ""),
                name=payload.get("name", "User"),
            )

    # Fallback to fetching user from redis by ID/email if token payload is unavailable
    redis = request.app.state.redis
    user = await get_user_by_email(redis, auth.user_id)
    if user:
        return UserResponse(id=user["id"], email=user["email"], name=user["name"])

    return UserResponse(id=auth.user_id, email="", name=auth.user_id)
