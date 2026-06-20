"""Stream Manager (Vol 4A §16, Vol 5 §13).

Bridges an LLM token stream to a resumable, buffered SSE feed:

  producer:  run_generation()  -> consumes provider.stream(), buffers tokens
  consumer:  sse()             -> replays buffered events then streams live,
                                  resumable from a client-supplied sequence id

Business logic must complete before streaming begins; the Stream Manager only
moves already-decided tokens (Vol 4A §16).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from app.domain.ai import LLMProvider, LLMRequest
from app.domain.errors import ProviderError

from .buffer import GenerationBuffer

logger = logging.getLogger(__name__)


def format_sse(event_type: str, data: dict, *, seq: int | None = None) -> str:
    """Render a Server-Sent Event. The ``id:`` field carries the sequence number
    so a reconnecting client can resume via the Last-Event-ID header."""
    lines = []
    if seq is not None:
        lines.append(f"id: {seq}")
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data)}")
    return "\n".join(lines) + "\n\n"


class StreamManager:
    def __init__(self, buffer: GenerationBuffer) -> None:
        self.buffer = buffer

    async def begin(self, session_id: str, message_id: str) -> bool:
        """Reserve the single active generation slot for a session."""
        return await self.buffer.begin(session_id, message_id)

    async def run_generation(
        self, provider: LLMProvider, request: LLMRequest, message_id: str
    ) -> str:
        """Consume the provider stream into the buffer. Returns the full text."""
        parts: list[str] = []
        try:
            async for chunk in provider.stream(request):
                if chunk.delta:
                    parts.append(chunk.delta)
                    await self.buffer.append_token(message_id, chunk.delta)
                if chunk.done:
                    break
            await self.buffer.complete(message_id)
        except ProviderError as exc:
            logger.warning("Generation failed for %s: %s", message_id, exc)
            await self.buffer.fail(message_id, str(exc))
            raise
        return "".join(parts)

    async def stream_text(self, message_id: str, text: str) -> None:
        """Emit an already-decided response into the buffer word-by-word.

        Per Vol 4A §16 the business decision (generation + validation) completes
        before streaming; this only *delivers* the settled tokens, which keeps
        validation off the token path and makes the stream trivially resumable."""
        for word in text.split(" "):
            await self.buffer.append_token(message_id, word + " ")
        await self.buffer.complete(message_id)

    async def fail(self, message_id: str, error: str) -> None:
        await self.buffer.fail(message_id, error)

    async def sse(self, message_id: str, after_seq: int = -1) -> AsyncIterator[str]:
        """Yield SSE strings for a message, resumable from ``after_seq``."""
        async for event in self.buffer.subscribe(message_id, after_seq):
            yield format_sse(event.type, {"message_id": message_id, **event.data}, seq=event.seq)
