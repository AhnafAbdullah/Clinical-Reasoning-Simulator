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


# ── Auth & access errors (Vol 5 §5/§7) ─────────────────────────────────────────


class AuthError(DomainError):
    """Base class for authentication/authorization failures."""


class InvalidCredentialsError(AuthError):
    """Email/password or token did not authenticate."""


class EmailAlreadyRegisteredError(AuthError):
    """Registration attempted with an email that already exists."""


class TokenError(AuthError):
    """A JWT or refresh token was missing, malformed, expired, or revoked."""


class PermissionDeniedError(AuthError):
    """Authenticated principal lacks the required role/ownership."""


# ── Session / workflow errors (Vol 4D, Vol 5 §7) ───────────────────────────────


class NotFoundError(DomainError):
    """A requested resource does not exist (maps to 404 / NOT_FOUND)."""


class RateLimitedError(DomainError):
    """A rate limit was exceeded (maps to 429 / RATE_LIMITED)."""


class SessionCompletedError(DomainError):
    """An action was attempted on a session that is no longer ACTIVE."""


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
