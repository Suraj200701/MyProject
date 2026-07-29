"""Async Redis client singleton + FastAPI dependency.

Used for: OTP storage, session cache, API response caching, rate limiting,
and as the Celery broker/result backend (see notifications/tasks.py).
"""

from collections.abc import AsyncGenerator

import redis.asyncio as redis

from config.settings import settings

_redis_pool: redis.ConnectionPool | None = None


def get_redis_pool() -> redis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.REDIS_URL, decode_responses=True, max_connections=50
        )
    return _redis_pool


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """FastAPI dependency yielding a Redis client bound to the shared pool."""
    client = redis.Redis(connection_pool=get_redis_pool())
    try:
        yield client
    finally:
        await client.aclose()


async def close_redis_pool() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None
