"""Settings guardrails: a non-development deployment must not boot on dev secrets."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_refuses_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="CRS_JWT_SECRET"):
        Settings(environment="production", _env_file=None)


def test_production_boots_with_real_jwt_secret() -> None:
    s = Settings(environment="production", jwt_secret="x" * 48, _env_file=None)
    assert s.environment == "production"


def test_development_allows_default_jwt_secret() -> None:
    assert Settings(environment="development", _env_file=None).jwt_secret
