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


# ── HTTP integration harness ─────────────────────────────────────────────────────


class _NoLimit:
    """Rate limiter stub used in tests (always allows)."""

    async def check(self, *args: object, **kwargs: object) -> None:
        return None


@pytest.fixture
def client(session, monkeypatch):
    """A TestClient wired to the in-memory DB, a fake-backed AIOS (real prompt
    rendering), an in-memory stream buffer, and a no-op rate limiter."""
    from contextlib import contextmanager

    from fastapi.testclient import TestClient

    from app.api import deps
    from app.main import app
    from app.modules.ai.aios import AIOS
    from app.modules.ai.buffer import InMemoryGenerationBuffer
    from app.modules.ai.stream_manager import StreamManager

    buffer = InMemoryGenerationBuffer()
    stream_manager = StreamManager(buffer)
    aios = AIOS(FakeProvider("I have had this chest pain for about two hours now."))

    @contextmanager
    def _test_scope():
        # Background persistence (conversation service) writes to the test session.
        yield session

    monkeypatch.setattr("app.modules.conversation.service.session_scope", _test_scope)
    # The evaluation worker also persists from a background task.
    monkeypatch.setattr("app.modules.evaluation.service.session_scope", _test_scope)
    # The SSE endpoint (and its detached auth) uses short-lived sessions of its
    # own so streaming never pins a pooled connection; point those here too.
    monkeypatch.setattr("app.api.deps.session_scope", _test_scope)
    monkeypatch.setattr("app.modules.conversation.router.session_scope", _test_scope)

    def _db_dep():
        yield session

    app.dependency_overrides[deps.get_db] = _db_dep
    app.dependency_overrides[deps.get_aios] = lambda: aios
    app.dependency_overrides[deps.get_stream_manager] = lambda: stream_manager
    app.dependency_overrides[deps.get_rate_limiter] = _NoLimit
    test_client = TestClient(app)
    test_client.buffer = buffer  # type: ignore[attr-defined]  # for assertions
    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client) -> dict[str, str]:
    """Register a student and return Authorization headers for them."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "student@example.com", "password": "supersecret123"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def published_case_id(session, sample_case):
    """Seed the sample case as a Published case in the test DB; return its id."""
    from app.domain.enums import Difficulty
    from app.infrastructure.repositories.case_repository import SqlAlchemyCaseRepository
    from app.modules.cases.use_cases import create_draft_case, publish_case

    repo = SqlAlchemyCaseRepository(session)
    meta = sample_case["metadata"]
    draft = create_draft_case(
        repo,
        title=meta["title"],
        difficulty=Difficulty(meta["difficulty"]),
        specialty=meta["specialty"],
        json_content=sample_case,
    )
    published = publish_case(repo, draft.id, reviewed_by="Dr. Test", reviewer_credentials="MBBS")
    return published.id
