"""Process-wide singletons for the AI subsystem (Vol 2A §9, Vol 4A).

The provider, generation buffer, stream manager and AIOS are stateless across
requests and expensive to build, so they are created once. FastAPI dependencies
(``app.api.deps``) hand these out and tests override them with fakes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import redis.asyncio as redis

from app.core.config import get_settings
from app.domain.ai import LLMProvider

if TYPE_CHECKING:
    from app.core.rate_limit import RateLimiter
from app.infrastructure.ai.openrouter import OpenRouterProvider
from app.infrastructure.ai.redis_buffer import RedisGenerationBuffer
from app.modules.ai.aios import AIOS
from app.modules.ai.buffer import GenerationBuffer
from app.modules.ai.stream_manager import StreamManager


@lru_cache
def get_redis() -> redis.Redis:
    """One connection-pooled Redis client shared by the generation buffer, the
    rate limiter and the readiness probe."""
    return redis.from_url(get_settings().redis_url, decode_responses=True)


@lru_cache
def get_provider() -> LLMProvider:
    return OpenRouterProvider(get_settings())


@lru_cache
def get_buffer() -> GenerationBuffer:
    return RedisGenerationBuffer(get_redis())


@lru_cache
def get_stream_manager() -> StreamManager:
    return StreamManager(get_buffer())


@lru_cache
def get_aios() -> AIOS:
    from app.infrastructure.ai.db_audit import DbAuditSink

    return AIOS(get_provider(), audit_sink=DbAuditSink())


@lru_cache
def get_rate_limiter() -> "RateLimiter":
    from app.core.rate_limit import RateLimiter

    return RateLimiter(get_redis())


async def shutdown() -> None:
    """Close shared network resources on app shutdown (called from the FastAPI
    lifespan). Creating a resource just to close it is harmless."""
    await get_redis().aclose()
    aclose = getattr(get_provider(), "aclose", None)
    if aclose is not None:
        await aclose()
