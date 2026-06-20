"""Retry Manager (Vol 4A §18).

Transient AI failures should not immediately fail the user request. The strategy
escalates: same model -> different model -> (different route) -> graceful failure,
with exponential backoff and a configurable cap.

Only transient failures are retried (provider errors, response-validation
rejections). Safety failures such as a knowledge-boundary violation are never
retried — they abort immediately.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.config import Settings, get_settings
from app.domain.errors import (
    GenerationExhaustedError,
    ProviderError,
    ResponseValidationError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

_RETRYABLE = (ProviderError, ResponseValidationError)


class RetryManager:
    def __init__(self, settings: Settings | None = None) -> None:
        s = settings or get_settings()
        self.max_retries = s.llm_max_retries
        self.backoff_base = s.llm_backoff_base_seconds

    def _plan(self, models: list[str]) -> list[str]:
        if not models:
            raise GenerationExhaustedError("No models available to attempt.")
        plan = [models[0]]
        for i in range(self.max_retries):
            plan.append(models[min(i + 1, len(models) - 1)])
        return plan

    async def run(self, models: list[str], attempt: Callable[[str], Awaitable[T]]) -> tuple[T, int]:
        """Execute ``attempt(model)`` across the escalation plan.

        Returns ``(result, retry_count)``; raises ``GenerationExhaustedError`` if
        every attempt fails.
        """
        plan = self._plan(models)
        last_exc: Exception | None = None
        for index, model in enumerate(plan):
            try:
                result = await attempt(model)
                return result, index
            except _RETRYABLE as exc:
                last_exc = exc
                logger.warning(
                    "AI attempt %d/%d failed on model %s: %s",
                    index + 1,
                    len(plan),
                    model,
                    exc,
                )
                if index < len(plan) - 1:
                    await asyncio.sleep(self.backoff_base * (2**index))
        raise GenerationExhaustedError(
            f"All {len(plan)} AI attempts failed; last error: {last_exc}"
        ) from last_exc
