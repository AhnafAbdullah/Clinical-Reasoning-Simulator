"""Audit + metrics sinks (Vol 4A §19-20).

Every AI interaction is auditable: agent, prompt version, model, provider,
tokens, latency, retries, validation outcome and estimated cost are recorded so
any call can be reconstructed and monitored. The sink is a port so the AIOS can
run with a logging sink (tests/dev) or a DB-backed sink (production) without
change.

Sensitive prompt content is not logged (Vol 4A §20 / §24).
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Protocol

from app.domain.ai import AIInteraction

logger = logging.getLogger("crs.ai.audit")


class AuditSink(Protocol):
    def record(self, interaction: AIInteraction) -> None: ...


class LoggingAuditSink:
    """Default sink: structured log line per AI call (no prompt content)."""

    def record(self, interaction: AIInteraction) -> None:
        logger.info("ai_call %s", asdict(interaction))


class CapturingAuditSink:
    """Test/dev sink that retains interactions in memory."""

    def __init__(self) -> None:
        self.interactions: list[AIInteraction] = []

    def record(self, interaction: AIInteraction) -> None:
        self.interactions.append(interaction)
