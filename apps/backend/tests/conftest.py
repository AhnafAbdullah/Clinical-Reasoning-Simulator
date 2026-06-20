from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.infrastructure.db.models  # noqa: F401  (register tables)
from app.core.config import get_settings
from app.domain.ai import LLMRequest, LLMResponse, LLMUsage, StreamChunk
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


# ── AI test doubles ────────────────────────────────────────────────────────────


class FakeProvider:
    """Configurable in-memory LLMProvider for AIOS tests.

    ``responder`` maps an LLMRequest to the text to return (default: fixed text).
    ``fail_times`` raises ProviderError on the first N calls (transient failure).
    """

    name = "fake"

    def __init__(
        self,
        text: str = "It started about two hours ago.",
        *,
        responder: Callable[[LLMRequest], str] | None = None,
        fail_times: int = 0,
        usage: LLMUsage | None = None,
    ) -> None:
        self._text = text
        self._responder = responder
        self._fail_times = fail_times
        self._usage = usage or LLMUsage(prompt_tokens=100, completion_tokens=20)
        self.calls = 0

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.calls <= self._fail_times:
            from app.domain.errors import ProviderError

            raise ProviderError(f"simulated transient failure #{self.calls}")
        text = self._responder(request) if self._responder else self._text
        return LLMResponse(text=text, model=request.model, usage=self._usage)

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        text = self._responder(request) if self._responder else self._text
        for word in text.split(" "):
            yield StreamChunk(delta=word + " ")
        yield StreamChunk(done=True, finish_reason="stop")

    async def health_check(self) -> bool:
        return True

    def estimate_cost(self, request: LLMRequest, usage: LLMUsage) -> float:
        return 0.0


@pytest.fixture
def fake_provider_cls() -> type[FakeProvider]:
    return FakeProvider
