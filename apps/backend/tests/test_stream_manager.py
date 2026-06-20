"""Stream Manager + generation buffer: buffering, resume, one-active-per-session."""

from __future__ import annotations

import asyncio

from app.domain.ai import LLMRequest
from app.modules.ai.buffer import InMemoryGenerationBuffer
from app.modules.ai.stream_manager import StreamManager, format_sse


def test_format_sse_carries_sequence_id() -> None:
    out = format_sse("token", {"token": "hi"}, seq=3)
    assert "id: 3" in out
    assert "event: token" in out
    assert '"token": "hi"' in out
    assert out.endswith("\n\n")


async def test_one_active_generation_per_session() -> None:
    buffer = InMemoryGenerationBuffer()
    assert await buffer.begin("session-1", "msg-a") is True
    # A second generation for the same session is refused while the first runs.
    assert await buffer.begin("session-1", "msg-b") is False
    await buffer.complete("msg-a")
    # Once the first finishes, a new generation may start.
    assert await buffer.begin("session-1", "msg-c") is True


async def test_buffer_replays_and_resumes_from_offset() -> None:
    buffer = InMemoryGenerationBuffer()
    s0 = await buffer.append_token("m", "Hello ")
    s1 = await buffer.append_token("m", "world")
    await buffer.complete("m")

    full = await buffer.snapshot("m", after_seq=-1)
    assert [e.type for e in full] == ["token", "token", "complete"]

    # A client that already saw seq s0 resumes and gets only the rest.
    resumed = await buffer.snapshot("m", after_seq=s0)
    assert [e.seq for e in resumed] == [s1, s1 + 1]


async def test_live_subscribe_receives_streamed_tokens() -> None:
    buffer = InMemoryGenerationBuffer()
    collected: list[str] = []

    async def consumer() -> None:
        async for event in buffer.subscribe("m", after_seq=-1):
            if event.type == "token":
                collected.append(event.data["token"])
            if event.terminal:
                return

    async def producer() -> None:
        for token in ["a", "b", "c"]:
            await buffer.append_token("m", token)
            await asyncio.sleep(0)
        await buffer.complete("m")

    await asyncio.wait_for(asyncio.gather(consumer(), producer()), timeout=2.0)
    assert collected == ["a", "b", "c"]


async def test_run_generation_buffers_provider_stream(fake_provider_cls) -> None:
    buffer = InMemoryGenerationBuffer()
    manager = StreamManager(buffer)
    provider = fake_provider_cls(text="one two three")
    request = LLMRequest(model="m", messages=[])

    text = await manager.run_generation(provider, request, "msg-1")
    assert text.strip() == "one two three"

    events = await buffer.snapshot("msg-1")
    assert events[-1].type == "complete"
    sse_chunks = [c async for c in manager.sse("msg-1")]
    assert any("event: complete" in c for c in sse_chunks)
