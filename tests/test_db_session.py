"""Engine + session factory smoke tests against the configured Postgres."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import text

from nagara.config import settings
from nagara.db.session import build_engine, build_sessionmaker


@pytest.fixture
def pg_engine() -> AsyncEngine:
    return build_engine(settings.get_postgres_dsn("asyncpg"))


def test_build_engine_returns_async_engine(pg_engine: AsyncEngine) -> None:
    assert isinstance(pg_engine, AsyncEngine)
    assert str(pg_engine.url).startswith("postgresql+asyncpg://")


@pytest.mark.asyncio
async def test_build_sessionmaker_yields_working_session(pg_engine: AsyncEngine) -> None:
    factory = build_sessionmaker(pg_engine)
    async with factory() as session:
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("select 1"))
        assert result.scalar_one() == 1
