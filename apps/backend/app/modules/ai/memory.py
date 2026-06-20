"""Memory Manager (Vol 4A §10-11).

Organises memory into layers and supplies only those a template declares:
  - recent_messages: the last N conversation turns, as chat messages;
  - session_summary: a compact textual recap of earlier turns;
  - extracted_clinical_facts: durable facts pulled out of the conversation.

Aggressive token reduction is the goal (Vol 4A §11): old turns are summarised
rather than replayed verbatim.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.domain.ai import ChatMessage, ChatRole


@dataclass(frozen=True)
class MemoryBundle:
    # Conversation turns appended after the system prompt (oldest -> newest),
    # ending with the current user message.
    messages_tail: list[ChatMessage] = field(default_factory=list)
    # Scalar/structured memory merged into the render variables.
    variables: dict[str, Any] = field(default_factory=dict)


class MemoryManager:
    def __init__(self, recent_window: int = 8) -> None:
        self.recent_window = recent_window

    def build(
        self,
        template_memory_layers: Sequence[str],
        *,
        history: Sequence[ChatMessage] = (),
        current_user_message: str | None = None,
        extracted_facts: Sequence[str] = (),
    ) -> MemoryBundle:
        layers = set(template_memory_layers)
        tail: list[ChatMessage] = []
        variables: dict[str, Any] = {}

        older = list(history)
        if "recent_messages" in layers and self.recent_window > 0:
            recent = older[-self.recent_window :]
            older = older[: -self.recent_window] if len(older) > self.recent_window else []
            tail.extend(recent)
        elif "recent_messages" not in layers:
            # Template does not want turns replayed; everything goes to summary.
            older = list(history)

        if "session_summary" in layers:
            variables["session_summary"] = self._summarise(older)

        if "extracted_clinical_facts" in layers:
            variables["extracted_clinical_facts"] = list(extracted_facts)

        if current_user_message is not None:
            tail.append(ChatMessage(role=ChatRole.USER, content=current_user_message))

        return MemoryBundle(messages_tail=tail, variables=variables)

    @staticmethod
    def _summarise(messages: Sequence[ChatMessage]) -> str:
        """MVP summariser: a compact bullet recap of earlier turns.

        Deliberately deterministic and non-LLM — heavier summarisation can be
        introduced later behind this same interface without touching callers.
        """
        if not messages:
            return ""
        lines = []
        for msg in messages:
            speaker = "Clinician" if msg.role == ChatRole.USER else "Patient"
            text = msg.content.strip().replace("\n", " ")
            if len(text) > 160:
                text = text[:157] + "..."
            lines.append(f"- {speaker}: {text}")
        return "\n".join(lines)
