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
