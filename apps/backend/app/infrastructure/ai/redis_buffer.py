"""Redis-backed generation buffer (Vol 4A §16, §23).

Stores each generation's events in a Redis list and a 'done' marker, so any
stateless API instance can serve or resume a stream — no session affinity. The
in-process implementation in ``app.modules.ai.buffer`` is used for tests and
single-process dev; this one is wired in production.

Liveness is delivered by short polling of the list; this is simple and robust.
A pub/sub fast-path can be layered on later without changing the port.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import redis.asyncio as redis

from app.core.config import get_settings
from app.modules.ai.buffer import COMPLETE, ERROR, TOKEN, BufferedEvent

_TTL_SECONDS = 60 * 30  # keep a finished generation around for late reconnects
_POLL_SECONDS = 0.1


def _as_str(value: str | bytes) -> str:
    return value.decode() if isinstance(value, bytes) else value


class RedisGenerationBuffer:
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._redis = client or redis.from_url(get_settings().redis_url, decode_responses=True)

    @staticmethod
    def _events_key(message_id: str) -> str:
        return f"gen:{message_id}:events"

    @staticmethod
    def _active_key(session_id: str) -> str:
        return f"gen:active:{session_id}"

    async def begin(self, session_id: str, message_id: str) -> bool:
        active = await self._redis.get(self._active_key(session_id))
        if active and not await self._is_done(_as_str(active)):
            return False
        await self._redis.set(self._active_key(session_id), message_id, ex=_TTL_SECONDS)
        return True

    async def _is_done(self, message_id: str) -> bool:
        last = await self._redis.lindex(self._events_key(message_id), -1)
        if last is None:
            return False
        return json.loads(last)["type"] in (COMPLETE, ERROR)

    async def _emit(self, message_id: str, etype: str, data: dict[str, str]) -> int:
        key = self._events_key(message_id)
        seq = await self._redis.rpush(key, json.dumps({"type": etype, "data": data})) - 1
        await self._redis.expire(key, _TTL_SECONDS)
        # Store the seq inside the entry now that we know it.
        await self._redis.lset(key, seq, json.dumps({"seq": seq, "type": etype, "data": data}))
        return seq

    async def append_token(self, message_id: str, token: str) -> int:
        return await self._emit(message_id, TOKEN, {"token": token})

    async def complete(self, message_id: str, finish_reason: str | None = None) -> None:
        await self._emit(message_id, COMPLETE, {"finish_reason": finish_reason or "stop"})

    async def fail(self, message_id: str, error: str) -> None:
        await self._emit(message_id, ERROR, {"error": error})

    async def snapshot(self, message_id: str, after_seq: int = -1) -> list[BufferedEvent]:
        start = after_seq + 1
        raw = await self._redis.lrange(self._events_key(message_id), start, -1)
        events: list[BufferedEvent] = []
        for offset, item in enumerate(raw):
            obj = json.loads(item)
            # An event is rpush'd then lset with its seq; tolerate the brief window
            # where a concurrent reader sees the entry before the seq is written by
            # deriving it from the list position.
            seq = obj.get("seq", start + offset)
            events.append(BufferedEvent(seq=seq, type=obj["type"], data=obj["data"]))
        return events

    async def subscribe(self, message_id: str, after_seq: int = -1) -> AsyncIterator[BufferedEvent]:
        cursor = after_seq
        while True:
            for event in await self.snapshot(message_id, cursor):
                cursor = event.seq
                yield event
                if event.terminal:
                    return
            await asyncio.sleep(_POLL_SECONDS)
