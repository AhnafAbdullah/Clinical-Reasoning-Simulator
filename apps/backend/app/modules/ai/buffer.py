"""Generation buffer (Vol 4A §16, Vol 4D §13).

A streamed generation is buffered as an ordered, append-only event log keyed by
``message_id``. Decoupling production (the LLM stream) from consumption (the SSE
connection) is what makes streaming *resumable*: a client that drops can
reconnect and replay from the last sequence number it saw, then continue live.

``GenerationBuffer`` is the port; ``InMemoryGenerationBuffer`` is the default
in-process implementation (used in tests/single-process dev). The Redis-backed
implementation lives in ``app.infrastructure.ai.redis_buffer`` for horizontal
scaling.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

TOKEN = "token"
COMPLETE = "complete"
ERROR = "error"
_TERMINAL = {COMPLETE, ERROR}


@dataclass(frozen=True)
class BufferedEvent:
    seq: int
    type: str  # token | complete | error
    data: dict[str, str]

    @property
    def terminal(self) -> bool:
        return self.type in _TERMINAL


class GenerationBuffer(Protocol):
    async def begin(self, session_id: str, message_id: str) -> bool:
        """Register an active generation. Returns False if the session already
        has an active (non-terminal) generation (one active per session)."""
        ...

    async def append_token(self, message_id: str, token: str) -> int: ...

    async def complete(self, message_id: str, finish_reason: str | None = None) -> None: ...

    async def fail(self, message_id: str, error: str) -> None: ...

    async def snapshot(self, message_id: str, after_seq: int = -1) -> list[BufferedEvent]: ...

    def subscribe(self, message_id: str, after_seq: int = -1) -> AsyncIterator[BufferedEvent]:
        """Yield events with seq > after_seq, replaying any already buffered then
        streaming new ones until a terminal event."""
        ...


class InMemoryGenerationBuffer:
    """Single-process implementation backed by asyncio primitives."""

    def __init__(self) -> None:
        self._events: dict[str, list[BufferedEvent]] = {}
        self._conds: dict[str, asyncio.Condition] = {}
        self._active: dict[str, str] = {}  # session_id -> message_id
        self._session_of: dict[str, str] = {}  # message_id -> session_id

    def _cond(self, message_id: str) -> asyncio.Condition:
        return self._conds.setdefault(message_id, asyncio.Condition())

    def _is_done(self, message_id: str) -> bool:
        events = self._events.get(message_id, [])
        return bool(events) and events[-1].terminal

    async def begin(self, session_id: str, message_id: str) -> bool:
        active = self._active.get(session_id)
        if active is not None and not self._is_done(active):
            return False
        self._events.setdefault(message_id, [])
        self._active[session_id] = message_id
        self._session_of[message_id] = session_id
        return True

    async def _emit(self, message_id: str, etype: str, data: dict[str, str]) -> int:
        events = self._events.setdefault(message_id, [])
        seq = len(events)
        events.append(BufferedEvent(seq=seq, type=etype, data=data))
        cond = self._cond(message_id)
        async with cond:
            cond.notify_all()
        return seq

    async def append_token(self, message_id: str, token: str) -> int:
        return await self._emit(message_id, TOKEN, {"token": token})

    async def complete(self, message_id: str, finish_reason: str | None = None) -> None:
        await self._emit(message_id, COMPLETE, {"finish_reason": finish_reason or "stop"})

    async def fail(self, message_id: str, error: str) -> None:
        await self._emit(message_id, ERROR, {"error": error})

    async def snapshot(self, message_id: str, after_seq: int = -1) -> list[BufferedEvent]:
        return [e for e in self._events.get(message_id, []) if e.seq > after_seq]

    async def subscribe(self, message_id: str, after_seq: int = -1) -> AsyncIterator[BufferedEvent]:
        cursor = after_seq
        cond = self._cond(message_id)
        while True:
            pending = await self.snapshot(message_id, cursor)
            for event in pending:
                cursor = event.seq
                yield event
                if event.terminal:
                    return
            async with cond:
                # Re-check before waiting to avoid missing a notification.
                if [e for e in self._events.get(message_id, []) if e.seq > cursor]:
                    continue
                await cond.wait()
