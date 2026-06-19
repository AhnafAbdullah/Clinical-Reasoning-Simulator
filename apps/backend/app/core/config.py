"""Application configuration. Everything is environment-driven (Vol 2A §16)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = .../clinical-reasoning-simulator ; this file is apps/backend/app/core/config.py
REPO_ROOT = Path(__file__).resolve().parents[4]
CASE_SCHEMA_DIR = REPO_ROOT / "packages" / "case-schema"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRS_", env_file=".env", extra="ignore")

    environment: str = "development"

    # Database. Defaults to local Postgres; tests override with sqlite.
    database_url: str = Field(
        default="postgresql+psycopg://crs:crs@localhost:5432/crs",
        description="SQLAlchemy database URL.",
    )
    sql_echo: bool = False

    # CORS — browser origins allowed to call the API (Vol 5 §25). Comma-separated.
    cors_origins: list[str] = ["http://localhost:3000"]

    # Paths
    case_schema_dir: Path = CASE_SCHEMA_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
