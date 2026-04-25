"""Async engine + session plumbing.

The module-level ``engine`` and ``async_session`` are wired against the
process-wide ``settings``. Routes consume the database via the bare
:func:`get_session` dependency — tests can swap it through FastAPI's
``app.dependency_overrides`` map without monkey-patching anything.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from nagara.config import settings
from nagara.lifespan import on_shutdown


def build_engine(url: str, **kwargs: object) -> AsyncEngine:
    """Build an ``AsyncEngine`` for the given URL."""
    return create_async_engine(url, **kwargs)


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build an ``async_sessionmaker`` bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# ── Process-wide singletons ────────────────────────────────────────────────
# ``application_name`` lands on every connection — visible in
# ``pg_stat_activity`` so DBAs can immediately tell API traffic apart from
# workers/scripts when debugging slow queries.
engine: AsyncEngine = build_engine(
    settings.get_postgres_dsn("asyncpg"),
    pool_size=settings.DATABASE_POOL_SIZE,
    pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
    connect_args={
        "server_settings": {"application_name": f"nagara.{settings.ENV.value}"}
    },
)
async_session: async_sessionmaker[AsyncSession] = build_sessionmaker(engine)


@on_shutdown
async def _dispose_engine(_app: FastAPI) -> None:
    """Return pooled connections cleanly on shutdown so Postgres doesn't log
    abrupt client disconnects and in-flight requests don't drop mid-query."""
    await engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields one ``AsyncSession`` per request.

    Auto-commits on a clean return; rolls back on any raised exception.
    Handlers don't have to remember ``await session.commit()`` — write
    your mutations and let the dependency close the transaction. Override
    in tests with ``app.dependency_overrides[get_session] = ...``.
    """
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
