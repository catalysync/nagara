"""Shared test fixtures.

Tests run against a **dedicated test database** (``nagara_test`` by default,
overridable via ``NAGARA_TEST_POSTGRES_DB``). Previously the suite targeted
the same DB as the dev server and the session-scoped fixture's
``drop_all`` + ``create_all`` blew away local dev data. Rails-style: the
dev DB and the test DB are separate; running tests never touches dev.

Each test gets a fresh ``AsyncSession`` bound to a dedicated connection
and outer transaction that rolls back on teardown — so tests can freely
commit inside the endpoint code under test without persisting state
across cases.

The schema is built once per pytest session via ``Base.metadata.drop_all``
+ ``create_all``. Migrations are not replayed here (the models are the
source of truth for test schema); the ``just test-integration`` path
exists for runs that need the full alembic chain.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Importing nagara.models registers every table on Base.metadata before
# create_all runs.
from nagara import models as _models  # noqa: F401  — side-effect import
from nagara.config import settings
from nagara.db import Base
from nagara.db.session import build_engine


def _test_db_name() -> str:
    """Resolve the test DB name.

    Order: ``NAGARA_TEST_POSTGRES_DB`` env if set, else the regular
    ``settings.POSTGRES_DB`` with a ``_test`` suffix (rails-style). Defaults
    to ``nagara_test`` since ``POSTGRES_DB`` defaults to ``nagara``.
    """
    explicit = os.environ.get("NAGARA_TEST_POSTGRES_DB")
    if explicit:
        return explicit
    return f"{settings.POSTGRES_DB}_test"


def _test_dsn() -> str:
    """Build an asyncpg DSN that points at the test DB instead of the dev DB."""
    base = settings.get_postgres_dsn("asyncpg")
    dev_db = settings.POSTGRES_DB
    test_db = _test_db_name()
    if base.rstrip("/").endswith(f"/{dev_db}"):
        return base[: -len(dev_db)] + test_db
    idx = base.rfind(dev_db)
    if idx == -1:
        raise RuntimeError(f"Cannot rewrite DSN for test DB: {base!r}")
    return base[:idx] + test_db + base[idx + len(dev_db) :]


@pytest_asyncio.fixture(scope="session")
async def _engine():
    """Session-scoped engine bound to the **test** DB. Builds the schema
    once, disposes at end. Never touches the dev DB."""
    engine = build_engine(_test_dsn())
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
