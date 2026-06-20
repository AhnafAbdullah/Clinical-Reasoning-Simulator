"""DB-backed audit sink (Vol 4A §20).

Persists each AI interaction to the ``audit_logs`` table. Used in production;
the AIOS falls back to the logging sink in tests/dev.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict

from app.core.db import session_scope
from app.domain.ai import AIInteraction
from app.infrastructure.db.models import AuditLog

logger = logging.getLogger("crs.ai.audit")


def _maybe_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


class DbAuditSink:
    def record(self, interaction: AIInteraction) -> None:
        try:
            with session_scope() as session:
                session.add(
                    AuditLog(
                        user_id=_maybe_uuid(interaction.user_id),
                        action="ai_call",
                        resource="ai",
                        resource_id=interaction.message_id or interaction.session_id,
                        audit_metadata=asdict(interaction),
                    )
                )
        except Exception:  # pragma: no cover - auditing must never break the request
            logger.exception("Failed to persist AI audit record")
