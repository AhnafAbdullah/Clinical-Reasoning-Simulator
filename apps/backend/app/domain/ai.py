"""Domain ports and value objects for the AI subsystem (Vol 4A).

These are framework-free contracts. Infrastructure (the OpenRouter adapter) and
the AIOS orchestration depend on these abstractions, never the other way round.
The LLM is an implementation detail behind the ``LLMProvider`` port (Principle 1,
Principle 8).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ModelProfile(str, Enum):
    """Abstract routing intent; the Model Router maps these to concrete models.

    The application asks for a profile, never a model name (Vol 4A §14).
    """

    DEFAULT = "default"
    REASONING = "reasoning"  # complex grading / generation
    LATENCY = "latency"  # fast, interactive patient turns


@dataclass(frozen=True)
class ChatMessage:
    role: ChatRole
    content: str


@dataclass(frozen=True)
class LLMRequest:
    """A provider-neutral generation request."""

    model: str
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int | None = None
    # Free-form correlation metadata for audit/metrics (never sent to the model).
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamChunk:
    """One token/delta of a streamed generation."""

    delta: str = ""
    done: bool = False
    usage: LLMUsage | None = None
    finish_reason: str | None = None


@runtime_checkable
class LLMProvider(Protocol):
    """The single AI provider port (Vol 4A §15). MVP = OpenRouter only.

    Changing providers must not require changes elsewhere in the application.
    """

    name: str

    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]: ...

    async def health_check(self) -> bool: ...

    def estimate_cost(self, request: LLMRequest, usage: LLMUsage) -> float: ...


# ── AIOS-level request/result (above the raw provider) ─────────────────────────


@dataclass(frozen=True)
class RenderedPrompt:
    """Output of the Prompt Renderer: the finished messages plus provenance.

    ``prompt_id``/``prompt_version`` are recorded on every interaction so any
    encounter can be reconstructed (Vol 4A Principle 6, Vol 4B §13).
    """

    prompt_id: str
    prompt_version: int
    messages: list[ChatMessage]
    output_type: str  # "plain_text" | "json"
    output_schema: str | None = None
    max_words: int | None = None


@dataclass(frozen=True)
class AIRequest:
    """An application request for an agent capability (Vol 4A §8).

    The application asks for an agent by capability and supplies the variables;
    it never selects prompts or models directly.
    """

    agent: str  # "patient" | "examiner" | ...
    variables: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    user_id: str | None = None
    message_id: str | None = None
    stream: bool = False


@dataclass(frozen=True)
class AIInteraction:
    """The auditable record of a single AI call (Vol 4A §20)."""

    agent: str
    prompt_id: str
    prompt_version: int
    profile: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    retry_count: int
    validation_status: str
    estimated_cost: float
    session_id: str | None = None
    user_id: str | None = None
    message_id: str | None = None


@dataclass(frozen=True)
class AIResult:
    text: str
    interaction: AIInteraction
