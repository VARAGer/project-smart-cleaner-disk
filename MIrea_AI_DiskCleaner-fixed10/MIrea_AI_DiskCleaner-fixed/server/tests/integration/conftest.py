"""
Integration test fixtures — use a real PostgreSQL database.

Set POSTGRES_TEST_URL to enable; otherwise all tests in this directory are
skipped. Example:

    POSTGRES_TEST_URL=postgresql+asyncpg://smartcleaner:smartcleaner_dev_pw@localhost:5432/smartcleaner_test

Isolation strategy: TRUNCATE `users` before every test (fast on Postgres,
no teardown races from dropped tables).
"""

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.db import Base, get_session
from main import app

POSTGRES_TEST_URL = os.environ.get(
    "POSTGRES_TEST_URL",
    "postgresql+asyncpg://smartcleaner:smartcleaner_dev_pw@localhost:5433/smartcleaner_test",
)

# Skip all integration tests if Postgres isn't reachable.
pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def pg_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Function-scoped engine. Session scope + asyncpg + pytest-asyncio don't
    play well together (each async test runs in its own event loop; session
    fixtures would attach connections to the wrong loop). Creating the engine
    per test costs ~50ms but eliminates all "attached to a different loop"
    flakiness.
    """
    from models import user  # noqa: F401

    engine = create_async_engine(
        POSTGRES_TEST_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

    # Narrow skip: only connection-level errors count as "Postgres isn't up".
    # Schema/permission errors are real bugs and must propagate.
    import socket

    from sqlalchemy.exc import InterfaceError, OperationalError

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (OperationalError, InterfaceError, ConnectionRefusedError, socket.gaierror) as e:
        await engine.dispose()
        pytest.skip(
            f"Postgres not reachable at {POSTGRES_TEST_URL}: {e}. "
            "Start it with `docker compose up -d postgres` and ensure the "
            "smartcleaner_test database exists.",
            allow_module_level=False,
        )

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session_factory(pg_engine):
    return async_sessionmaker(
        pg_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture(autouse=True)
async def _truncate_tables(pg_engine):
    """Wipe state between tests so each starts from an empty schema."""
    async with pg_engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
    yield


@pytest_asyncio.fixture
async def pg_session(pg_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with pg_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def pg_client(pg_session_factory) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI client that talks to the Postgres test DB."""

    async def override_get_session():
        async with pg_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
