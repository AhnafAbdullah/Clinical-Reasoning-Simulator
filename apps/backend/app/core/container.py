"""Process-wide singletons for the AI subsystem (Vol 2A §9, Vol 4A).

The provider, generation buffer, stream manager and AIOS are stateless across
requests and expensive to build, so they are created once. FastAPI dependencies
(``app.api.deps``) hand these out and tests override them with fakes.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

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
def get_provider() -> LLMProvider:
    return OpenRouterProvider(get_settings())


@lru_cache
def get_buffer() -> GenerationBuffer:
    return RedisGenerationBuffer()


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

    return RateLimiter()
