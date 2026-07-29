"""Liveness / readiness endpoints."""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from database.session import get_db
from redis_cache.client import get_redis

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}


@router.get("/health/ready")
async def readiness(
    db: AsyncSession = Depends(get_db),
    cache: Redis = Depends(get_redis),
) -> dict:
    """Checks real connectivity to Postgres and Redis, not just process liveness."""
    checks = {"database": "down", "redis": "down"}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "up"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"error: {exc}"

    try:
        await cache.ping()
        checks["redis"] = "up"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc}"

    status = "ok" if all(v == "up" for v in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
