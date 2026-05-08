"""
SQLAlchemy 2.0 async engine. Supports both SQLite (study/local) and
PostgreSQL+asyncpg (docker-compose / production).

The engine kwargs differ: SQLite doesn't accept QueuePool options, Postgres
benefits from explicit pool tuning + pre_ping to survive idle disconnects.
"""

import os

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _engine_kwargs(url: str) -> dict:
    if _is_sqlite(url):
        return {"echo": False}
    # Postgres (or any non-sqlite) — real pool.
    return {
        "echo": False,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }


if _is_sqlite(DATABASE_URL):
    os.makedirs("data", exist_ok=True)

engine = create_async_engine(DATABASE_URL, **_engine_kwargs(DATABASE_URL))

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    from models import user  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
