"""Pytest fixtures: a dedicated `leadmaster_test` database (created fresh
per test session), truncated between tests for isolation, plus an async
HTTP client wired to the real FastAPI app via ASGI transport (no mocking
of the app itself — this exercises the real routing/dependency/ORM
stack end-to-end, just against a disposable database)."""

import os
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

os.environ["POSTGRES_DB"] = "leadmaster_test"

from config.settings import get_settings  # noqa: E402

get_settings.cache_clear()
from config import settings as settings_module  # noqa: E402

settings_module.settings = get_settings()

from database import session as db_session_module  # noqa: E402

db_session_module.engine = create_async_engine(settings_module.settings.DATABASE_URL, echo=False)
db_session_module.AsyncSessionLocal = async_sessionmaker(
    bind=db_session_module.engine, expire_on_commit=False, autoflush=False
)

from database.base import Base  # noqa: E402
from main import app  # noqa: E402
from models import *  # noqa: E402,F401,F403
from scripts.seed_data import seed  # noqa: E402


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _setup_database():
    engine = db_session_module.engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await seed()
    yield
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Truncates all business-data tables before every test, but leaves
    the seeded reference data (roles/permissions/plans/providers) intact."""
    yield
    engine = db_session_module.engine
    keep = {"roles", "permissions", "role_permissions", "subscription_plans", "api_providers"}
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        tables = [row[0] for row in result if row[0] not in keep and row[0] != "alembic_version"]
        if tables:
            await conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def signed_up_user(client: AsyncClient):
    """Signs up a fresh user + org and returns (tokens_json, headers)."""
    email = f"user_{uuid.uuid4().hex[:10]}@example.com"
    resp = await client.post(
        "/api/v1/auth/signup",
        json={
            "email": email,
            "password": "TestPass123",
            "full_name": "Test User",
            "company_name": "Test Org",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    return data, headers
