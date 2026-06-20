"""Application configuration. Everything is environment-driven (Vol 2A §16)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = .../clinical-reasoning-simulator ; this file is apps/backend/app/core/config.py
REPO_ROOT = Path(__file__).resolve().parents[4]
CASE_SCHEMA_DIR = REPO_ROOT / "packages" / "case-schema"
PROMPT_REGISTRY_DIR = REPO_ROOT / "packages" / "prompt-registry"


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

    # Feature flags (Vol 2B §31-32).
    enable_streaming: bool = True
    enable_google_login: bool = False
    enable_evaluation: bool = True
    enable_analytics: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
