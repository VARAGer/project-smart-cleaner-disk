"""
Shared pytest fixtures.

Env vars are set at import time (before app modules load config).
DB is in-memory SQLite; AsyncClient uses ASGITransport so no network is involved.
"""

import os

# Must run BEFORE any `from config import ...` in app modules.
# ENV=test relaxes prod fail-fast checks AND auto-disables the slowapi
# rate limiter so tests can hammer endpoints without 429s.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key-longer-than-32-characters")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("AI_PROVIDER", "gemini")
# Faster bcrypt under tests — production sets this to 13 in config.
os.environ.setdefault("BCRYPT_ROUNDS", "4")

from typing import AsyncGenerator  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from database.db import Base, get_session  # noqa: E402
from main import app  # noqa: E402


@pytest_asyncio.fixture
async def test_engine():
    # Import models so they register on Base.metadata.
    from models import user  # noqa: F401

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture
async def test_session(test_session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a user and return {user_id, username, access_token, token_type}."""
    response = await client.post(
        "/api/auth/register",
        json={"username": "test_user", "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return response.json()
