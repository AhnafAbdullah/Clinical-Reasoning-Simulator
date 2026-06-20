"""Redis-backed generation buffer parity, exercised against fakeredis."""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from app.infrastructure.ai.redis_buffer import RedisGenerationBuffer


@pytest.fixture
def buffer() -> RedisGenerationBuffer:
    return RedisGenerationBuffer(fakeredis.aioredis.FakeRedis(decode_responses=True))


async def test_one_active_generation_per_session(buffer: RedisGenerationBuffer) -> None:
    assert await buffer.begin("s1", "m1") is True
    assert await buffer.begin("s1", "m2") is False
    await buffer.complete("m1")
    assert await buffer.begin("s1", "m3") is True


async def test_append_complete_and_resume(buffer: RedisGenerationBuffer) -> None:
    await buffer.begin("s1", "m1")
    s0 = await buffer.append_token("m1", "Hello ")
    await buffer.append_token("m1", "world")
    await buffer.complete("m1")

    full = await buffer.snapshot("m1")
    assert [e.type for e in full] == ["token", "token", "complete"]
    assert full[0].seq == 0

    # Resume from the first token: only later events come back.
    resumed = await buffer.snapshot("m1", after_seq=s0)
    assert [e.type for e in resumed] == ["token", "complete"]


async def test_subscribe_replays_finished_generation(buffer: RedisGenerationBuffer) -> None:
    await buffer.begin("s1", "m1")
    await buffer.append_token("m1", "a")
    await buffer.fail("m1", "boom")

    collected = []
    async for event in buffer.subscribe("m1", after_seq=-1):
        collected.append(event)
        if event.terminal:
            break
    assert [e.type for e in collected] == ["token", "error"]
    assert collected[-1].data["error"] == "boom"
