"""Redis-backed fixed-window rate limiting (Vol 5 §24).

A single Redis counter per (action, principal, window) is cheap and good enough
for the MVP. Limiting is *fail-open*: if Redis is unavailable the request is
allowed (with a warning) rather than erroring — availability beats strictness for
a throttle. Disable entirely with ``CRS_RATE_LIMIT_ENABLED=false``.
"""

from __future__ import annotations

import logging
import time

import redis.asyncio as redis

from app.core.config import get_settings
from app.domain.errors import RateLimitedError

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, client: redis.Redis | None = None) -> None:
        self._settings = get_settings()
        self._redis = client or redis.from_url(self._settings.redis_url, decode_responses=True)

    async def check(self, action: str, principal: str, *, limit: int, window_seconds: int) -> None:
        if not self._settings.rate_limit_enabled or limit <= 0:
            return
        window = int(time.time()) // window_seconds
        key = f"rl:{action}:{principal}:{window}"
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, window_seconds)
        except Exception:  # pragma: no cover - fail open on Redis trouble
            logger.warning("Rate limiter unavailable; allowing request for %s", action)
            return
        if count > limit:
            raise RateLimitedError(f"Rate limit exceeded for {action}. Try again shortly.")
