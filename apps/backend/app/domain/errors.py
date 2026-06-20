"""Domain-level errors (framework-agnostic)."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for domain rule violations."""


class CaseValidationError(DomainError):
    """Case JSON failed schema or structural validation."""


class CaseImmutableError(DomainError):
    """Attempted to mutate a published (immutable) case."""


class CasePublishError(DomainError):
    """Preconditions for publishing a case were not met."""


class InvalidStateTransition(DomainError):
    """Attempted an illegal session state/stage transition."""


# ── AI subsystem errors (Vol 4A/4B) ────────────────────────────────────────────


class AIError(DomainError):
    """Base class for AI subsystem failures."""


class PromptNotFoundError(AIError):
    """Requested prompt id/version is absent from the registry."""


class PromptRenderError(AIError):
    """Template failed to render (e.g. undefined variable, missing include)."""


class KnowledgeBoundaryError(AIError):
    """Forbidden context appeared in a rendered prompt; generation is aborted.

    This is the single most important safety property of the patient prompt
    (Vol 4B §9) — enforced in software, before the model is ever called.
    """


class ResponseValidationError(AIError):
    """An AI response failed hot-path validation (Vol 4A §17)."""


class ProviderError(AIError):
    """The LLM provider failed (transient or terminal)."""


class GenerationExhaustedError(AIError):
    """All retries/fallbacks were exhausted (Vol 4A §18)."""
