"""Smoke: Postgres is reachable, schema is created, raw SQL works."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_postgres_version_query(pg_session: AsyncSession):
    result = await pg_session.execute(text("SELECT version()"))
    version_string = result.scalar_one()
    assert "PostgreSQL" in version_string


async def test_users_table_exists(pg_session: AsyncSession):
    result = await pg_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'users' ORDER BY ordinal_position"
        )
    )
    cols = [row[0] for row in result.all()]
    assert cols == ["id", "username", "password_hash", "created_at"]


async def test_username_unique_constraint(pg_session: AsyncSession):
    """DB enforces UNIQUE(username) independently of the app layer."""
    from models.user import User

    u1 = User(
        id="id-1" + "0" * 32,  # padded, exactly 36 chars per schema
        username="dup_user",
        password_hash="h1",
    )
    u2 = User(
        id="id-2" + "0" * 32,
        username="dup_user",
        password_hash="h2",
    )
    pg_session.add(u1)
    await pg_session.commit()

    pg_session.add(u2)
    from sqlalchemy.exc import IntegrityError

    import pytest

    with pytest.raises(IntegrityError):
        await pg_session.commit()
    await pg_session.rollback()


async def test_created_at_preserves_timezone(pg_session: AsyncSession):
    """DateTime(timezone=True) round-trips tz-aware datetimes."""
    from models.user import User

    u = User(username="tz_user", password_hash="h")
    pg_session.add(u)
    await pg_session.commit()
    await pg_session.refresh(u)
    assert u.created_at.tzinfo is not None
