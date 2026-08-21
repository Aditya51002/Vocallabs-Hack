import secrets
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(value: str) -> list[str]:
    """Parse a comma-separated CORS allow-list and reject wildcard origins."""

    origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
    if not origins:
        raise ValueError("cors_origin must include at least one allowed origin")

    for origin in origins:
        if "*" in origin:
            raise ValueError("cors_origin must not contain wildcard origins")
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"Invalid CORS origin: {origin}")
        if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
            raise ValueError(f"CORS origin must not include a path or query: {origin}")

    return origins


class Settings(BaseSettings):
    groq_api_key: str = ""
    gemini_api_key: str = ""
    tavily_api_key: str = ""
    groq_model: str = "qwen/qwen3.6-27b"
    groq_model_small: str = "qwen/qwen3.6-27b"
    gemini_model: str = "gemini-3.6-flash"
    groq_rpm_budget: int = 28
    gemini_rpm_budget: int = 14
    redis_url: str = "redis://redis:6379/0"
    cors_origin: str = "http://localhost:3000"
    api_keys: SecretStr = Field(
        default=SecretStr(""),
        validation_alias="RESEARCHSWARM_API_KEYS",
    )
    jwt_secret: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(48)),
        validation_alias="RESEARCHSWARM_JWT_SECRET",
    )
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 24 * 7
    auth_rate_limit: int = 10
    auth_rate_window_seconds: int = 60
    max_researchers: int = 3
    session_rate_limit: int = 10
    session_rate_window_seconds: int = 60
    task_claim_ttl_seconds: int = 0
    task_claim_retry_buffer_seconds: int = 300
    task_claim_min_ttl_seconds: int = 120

    @field_validator("cors_origin")
    @classmethod
    def validate_cors_origin(cls, value: str) -> str:
        parse_cors_origins(value)
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
