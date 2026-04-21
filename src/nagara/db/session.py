"""Async engine + session plumbing.

The module-level ``engine`` and ``async_session`` are wired against the
process-wide ``settings`` so callers can ``from nagara.db.session import
get_session`` and inject it as a FastAPI dependency. Tests can build their own
engine via :func:`build_engine` to point at SQLite or a throwaway DB.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import partial

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nagara.config import settings


def build_engine(url: str, **kwargs: object) -> AsyncEngine:
    """Build an ``AsyncEngine`` for the given URL. Pool kwargs come from the
    process settings unless overridden."""
    return create_async_engine(url, **kwargs)


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build an ``async_sessionmaker`` bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """FastAPI-style dependency. Use as::

    SessionDep = Annotated[AsyncSession, Depends(partial(get_session, async_session))]
    """
    async with factory() as session:
        yield session


# ── Process-wide singletons ────────────────────────────────────────────────
# Built lazily on first import so test runs don't need a live database to
# import the module.
engine: AsyncEngine = build_engine(
    settings.get_postgres_dsn("asyncpg"),
    pool_size=settings.DATABASE_POOL_SIZE,
    pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
)
async_session: async_sessionmaker[AsyncSession] = build_sessionmaker(engine)

# Convenient pre-bound dependency for routes that just want a session.
session_dependency = partial(get_session, async_session)
