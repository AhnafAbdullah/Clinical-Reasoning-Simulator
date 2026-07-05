"""Application configuration. Everything is environment-driven (Vol 2A §16)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = .../clinical-reasoning-simulator ; this file is apps/backend/app/core/config.py
REPO_ROOT = Path(__file__).resolve().parents[4]
CASE_SCHEMA_DIR = REPO_ROOT / "packages" / "case-schema"
PROMPT_REGISTRY_DIR = REPO_ROOT / "packages" / "prompt-registry"

# Dev-only JWT secret. Any non-development environment MUST override it; the
# validator below refuses to boot otherwise.
_DEV_JWT_SECRET = "dev-insecure-secret-change-me-in-production-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRS_", env_file=".env", extra="ignore")

    environment: str = "development"

    # Database. Defaults to local Postgres; tests override with sqlite.
    database_url: str = Field(
        default="postgresql+psycopg://crs:crs@localhost:5432/crs",
        description="SQLAlchemy database URL.",
    )
    sql_echo: bool = False

    # Redis — generation buffer for resumable streaming + rate limiting (Vol 4A §16).
    redis_url: str = "redis://localhost:6379/0"

    # CORS — browser origins allowed to call the API (Vol 5 §25). Comma-separated.
    cors_origins: list[str] = ["http://localhost:3000"]

    # Paths
    case_schema_dir: Path = CASE_SCHEMA_DIR
    prompt_registry_dir: Path = PROMPT_REGISTRY_DIR

    # ── AIOS / LLM provider (Vol 4A §15/§21) ───────────────────────────────────
    # OpenRouter is the single MVP provider (ADR-0002). Key is server-side only.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Optional attribution headers OpenRouter recommends.
    openrouter_app_url: str = "http://localhost:3000"
    openrouter_app_title: str = "Clinical Reasoning Simulator"

    # Model routing profiles -> concrete OpenRouter model ids (Vol 4A §14).
    # The application never hardcodes model names; it asks for a profile.
    model_default: str = "openai/gpt-4o-mini"
    model_reasoning: str = "openai/gpt-4o"
    model_latency: str = "openai/gpt-4o-mini"

    # Generation defaults.
    llm_timeout_seconds: float = 60.0
    llm_temperature_patient: float = 0.7
    llm_temperature_examiner: float = 0.2
    llm_max_tokens: int = 1024

    # Retry policy (Vol 4A §18).
    llm_max_retries: int = 2
    llm_backoff_base_seconds: float = 0.5

    # ── Auth / JWT (Vol 5 §5) ──────────────────────────────────────────────────
    # Short-lived access token + rotating refresh token (Argon2 password hashing).
    # >= 32 bytes so HS256 is happy; override in every real environment.
    jwt_secret: str = _DEV_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14
    # Google OAuth (behind enable_google_login). Server-side only.
    google_client_id: str = ""
    google_client_secret: str = ""

    # ── Rate limiting (Vol 5 §24) — Redis-backed, per-user/per-action ──────────
    rate_limit_enabled: bool = True
    rate_limit_messages_per_minute: int = 20
    rate_limit_sessions_per_hour: int = 30
    rate_limit_investigations_per_minute: int = 30
    # Login is limited on two axes: per-email stops brute-forcing one account,
    # per-IP stops spraying one attempt across many accounts.
    rate_limit_login_per_minute: int = 10
    rate_limit_login_per_ip_per_minute: int = 30
    rate_limit_register_per_ip_per_hour: int = 10
    rate_limit_refresh_per_ip_per_minute: int = 30

    # Feature flags (Vol 2B §31-32).
    enable_streaming: bool = True
    enable_google_login: bool = False
    enable_evaluation: bool = True
    enable_analytics: bool = False

    @model_validator(mode="after")
    def _refuse_dev_secrets_outside_development(self) -> "Settings":
        """Fail at boot, not at exploit time: a deployment that forgot to set a
        real JWT secret must not come up able to mint forgeable tokens."""
        if self.environment not in ("development", "test") and self.jwt_secret == _DEV_JWT_SECRET:
            raise ValueError(
                "CRS_JWT_SECRET is still the built-in development value; set a strong "
                f"unique secret when CRS_ENVIRONMENT={self.environment!r}."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
