"""Redis-backed fixed-window rate limiting middleware.

Applies a global per-IP request budget to every request. Endpoints that
need a stricter budget (login, OTP request/verify) layer an additional
check via `check_rate_limit()` inside the route itself.
"""

import time

from fastapi import status
from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config.settings import settings
from redis_cache.client import get_redis_pool

EXEMPT_PATHS = {"/docs", "/redoc", "/openapi.json", f"{settings.API_V1_PREFIX}/health"}


async def check_rate_limit(redis: Redis, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Fixed-window counter. Returns (allowed, remaining)."""
    bucket = int(time.time() // window_seconds)
    redis_key = f"ratelimit:{key}:{bucket}"

    count = await redis.incr(redis_key)
    if count == 1:
        await redis.expire(redis_key, window_seconds)

    remaining = max(0, limit - count)
    return count <= limit, remaining


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        redis = Redis(connection_pool=get_redis_pool())
        try:
            allowed, remaining = await check_rate_limit(
                redis, f"global:{client_ip}", settings.RATE_LIMIT_PER_MINUTE, 60
            )
        except Exception:
            # Redis unavailable: fail open rather than blocking all traffic.
            return await call_next(request)
        finally:
            await redis.aclose()

        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"success": False, "message": "Too many requests. Please slow down.", "errors": None},
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
