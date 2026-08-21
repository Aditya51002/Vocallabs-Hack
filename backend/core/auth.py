"""User authentication, password hashing, user persistence in Redis, and JWT handling."""

from __future__ import annotations

import re
import time
from uuid import uuid4

import bcrypt
import jwt

from config import settings

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_input(email: str, name: str, password: str) -> tuple[str, str]:
    """Validate and sanitize signup inputs."""

    clean_email = email.strip().lower()
    clean_name = name.strip()

    if not clean_email or len(clean_email) > 254 or not EMAIL_REGEX.match(clean_email):
        raise ValueError("invalid_email")

    if not clean_name or len(clean_name) > 80:
        raise ValueError("invalid_name")

    if len(password) < 8:
        raise ValueError("password_too_short")

    if len(password.encode("utf-8")) > 72:
        raise ValueError("password_too_long")

    return clean_email, clean_name


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""

    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""

    try:
        pwd_bytes = password.encode("utf-8")
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(user: dict) -> str:
    """Generate a JWT access token for a user."""

    now = int(time.time())
    expires = now + (settings.jwt_expires_minutes * 60)

    payload = {
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"],
        "iat": now,
        "exp": expires,
    }

    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if not isinstance(payload, dict) or "sub" not in payload:
            return None
        return payload
    except jwt.PyJWTError:
        return None


async def create_user(redis, *, email: str, name: str, password: str) -> dict:
    """Create and persist a new user in Redis."""

    clean_email, clean_name = validate_user_input(email, name, password)
    user_key = f"user:{clean_email}"

    existing = await redis.hgetall(user_key)
    if existing:
        raise ValueError("email_taken")

    user_id = f"usr_{uuid4().hex[:12]}"
    password_hash = hash_password(password)
    created_at = int(time.time())

    user_data = {
        "id": user_id,
        "email": clean_email,
        "name": clean_name,
        "password_hash": password_hash,
        "created_at": str(created_at),
    }

    await redis.hset(user_key, mapping=user_data)

    return {
        "id": user_id,
        "email": clean_email,
        "name": clean_name,
        "created_at": created_at,
    }


async def get_user_by_email(redis, email: str) -> dict | None:
    """Fetch a user profile by email from Redis."""

    clean_email = email.strip().lower()
    user_key = f"user:{clean_email}"

    data = await redis.hgetall(user_key)
    if not data:
        return None

    # Handle bytes or string dict returned by redis client
    user_dict = {
        (k.decode("utf-8") if isinstance(k, bytes) else k): (
            v.decode("utf-8") if isinstance(v, bytes) else v
        )
        for k, v in data.items()
    }

    return {
        "id": user_dict["id"],
        "email": user_dict["email"],
        "name": user_dict["name"],
        "created_at": int(user_dict.get("created_at", 0)),
    }


async def authenticate_user(redis, *, email: str, password: str) -> dict | None:
    """Authenticate a user by email and password."""

    clean_email = email.strip().lower()
    user_key = f"user:{clean_email}"

    data = await redis.hgetall(user_key)
    if not data:
        return None

    user_dict = {
        (k.decode("utf-8") if isinstance(k, bytes) else k): (
            v.decode("utf-8") if isinstance(v, bytes) else v
        )
        for k, v in data.items()
    }

    password_hash = user_dict.get("password_hash", "")
    if not verify_password(password, password_hash):
        return None

    return {
        "id": user_dict["id"],
        "email": user_dict["email"],
        "name": user_dict["name"],
        "created_at": int(user_dict.get("created_at", 0)),
    }
