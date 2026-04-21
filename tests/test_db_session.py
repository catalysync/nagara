"""Engine + session factory smoke tests — uses an in-memory SQLite engine."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.sql import text

from nagara.db.session import build_engine, build_sessionmaker, get_session


@pytest.fixture
def sqlite_engine() -> AsyncEngine:
    return build_engine("sqlite+aiosqlite:///:memory:")


def test_build_engine_returns_async_engine(sqlite_engine: AsyncEngine) -> None:
    assert isinstance(sqlite_engine, AsyncEngine)
    assert str(sqlite_engine.url).startswith("sqlite+aiosqlite://")


@pytest.mark.asyncio
async def test_build_sessionmaker_yields_working_session(sqlite_engine: AsyncEngine) -> None:
    factory = build_sessionmaker(sqlite_engine)
    async with factory() as session:
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("select 1"))
        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_get_session_dependency_yields_then_closes(sqlite_engine: AsyncEngine) -> None:
    factory = build_sessionmaker(sqlite_engine)
    gen: AsyncIterator[AsyncSession] = get_session(factory)
    session = await anext(gen)
    assert isinstance(session, AsyncSession)
    # Session should be usable inside the dependency scope.
    result = await session.execute(text("select 1"))
    assert result.scalar_one() == 1
    # Exhausting the generator closes it cleanly.
    with pytest.raises(StopAsyncIteration):
        await anext(gen)
