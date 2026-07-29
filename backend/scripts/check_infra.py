"""Quick standalone connectivity check for Postgres + Redis (dev sanity check)."""

import asyncio

import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from config.settings import settings


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version()"))
        print("Postgres OK:", result.scalar())
    await engine.dispose()

    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    await r.set("infra_check", "ok")
    value = await r.get("infra_check")
    print("Redis OK:", value)
    await r.aclose()


if __name__ == "__main__":
    asyncio.run(main())
