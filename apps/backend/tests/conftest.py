from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.infrastructure.db.models  # noqa: F401  (register tables)
from app.core.config import get_settings
from app.infrastructure.db.base import Base


@pytest.fixture
def session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    s = factory()
    try:
        yield s
    finally:
        s.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def sample_case() -> dict:
    path: Path = get_settings().case_schema_dir / "examples" / "acs_chest_pain_basic.case.json"
    return json.loads(path.read_text(encoding="utf-8"))
