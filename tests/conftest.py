"""Shared test fixtures.

Tests run against the configured Postgres (``NAGARA_POSTGRES_*`` env vars).
Each test gets a fresh ``AsyncSession`` bound to a dedicated connection and
outer transaction that rolls back on teardown — so tests can freely commit
inside the endpoint code under test without persisting state across cases.

The schema is built once per pytest session via ``Base.metadata.drop_all`` +
``create_all``. Migrations are not replayed here (the models are the source
of truth for test schema); the ``just test-integration`` path exists for
runs that need the full alembic chain.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Importing nagara.models registers every table on Base.metadata before
# create_all runs.
from nagara import models as _models  # noqa: F401  — side-effect import
from nagara.config import settings
from nagara.db import Base
from nagara.db.session import build_engine


@pytest_asyncio.fixture(scope="session")
async def _engine():
    """Session-scoped engine. Builds the schema once, disposes at end."""
    engine = build_engine(settings.get_postgres_dsn("asyncpg"))
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(_engine) -> AsyncIterator[AsyncSession]:
    """Function-scoped session bound to an outer transaction that gets rolled
    back on teardown. ``join_transaction_mode="create_savepoint"`` means any
    ``session.commit()`` inside endpoint code under test wraps in a savepoint
    and does not end the outer transaction — state evaporates cleanly
    between tests.
    """
    async with _engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint",
        )
        async with factory() as s:
            yield s
        await trans.rollback()
