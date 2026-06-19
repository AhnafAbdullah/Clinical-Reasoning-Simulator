"""Phase 0B walking skeleton: proves the streaming + correlation-id plumbing
(Vol 5 §12-13) end-to-end before any real AI is wired in.

This is intentionally a stub and will be REPLACED in Phase 3 by the real
conversation/streaming workflow (Redis-buffered, OpenRouter-backed). It keeps no
real session state and simply echoes the submitted message back token-by-token.
"""

from __future__ import annotations

import asyncio
import json
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/_skeleton", tags=["skeleton"])

# In-process store standing in for the future Redis generation buffer.
_pending: dict[str, str] = {}


class MessageIn(BaseModel):
    message: str


class MessageAccepted(BaseModel):
    message_id: str
    status: str = "GENERATING"


@router.post("/messages", status_code=202, response_model=MessageAccepted)
def accept_message(body: MessageIn) -> MessageAccepted:
    """Accept a turn and return a correlation id; generation is streamed separately."""
    message_id = str(uuid.uuid4())
    _pending[message_id] = body.message
    return MessageAccepted(message_id=message_id)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def stream(message_id: str) -> StreamingResponse:
    """Stream the response for a given message_id as Server-Sent Events."""
    text = _pending.pop(message_id, None)

    async def gen():
        if text is None:
            yield _sse("error", {"message_id": message_id, "error": "UNKNOWN_MESSAGE_ID"})
            return
        echo = f"You said: {text}"
        for token in echo.split(" "):
            await asyncio.sleep(0.02)
            yield _sse("token", {"message_id": message_id, "token": token + " "})
        yield _sse("complete", {"message_id": message_id})

    return StreamingResponse(gen(), media_type="text/event-stream")
