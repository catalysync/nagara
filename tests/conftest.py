"""Shared test fixtures.

The ``session`` fixture spins up an in-memory SQLite engine, applies
``Base.metadata.create_all``, and yields a clean ``AsyncSession`` per test.
Fast, isolated, and zero infra dependency for model-level tests.

Tests that exercise Postgres-only behavior (jsonb operators, partial indexes,
inet columns, ...) should opt into a real Postgres engine via a fixture in
their own module — don't shoehorn that into this generic fixture.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

# Importing nagara.models registers every table on Base.metadata before
# create_all runs.
from nagara import models as _models  # noqa: F401  — side-effect import
from nagara.db import Base
from nagara.db.session import build_engine, build_sessionmaker


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = build_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = build_sessionmaker(engine)
    async with factory() as s:
        yield s
    await engine.dispose()
