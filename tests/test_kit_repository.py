from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

import pytest
from sqlalchemy import DateTime, String, Uuid
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from nagara.kit.repository import (
    RepositoryBase,
    RepositorySoftDeletionMixin,
    RepositorySortingMixin,
)


class _Base(DeclarativeBase):
    pass


class _Item(_Base):
    __tablename__ = "test_items"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class _SortBy(StrEnum):
    name = "name"


class _Repo(
    RepositorySortingMixin[_Item, _SortBy],
    RepositorySoftDeletionMixin[_Item],  # ty:ignore[invalid-type-arguments]
    RepositoryBase[_Item],  # ty:ignore[invalid-type-arguments]
):
    model = _Item


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(_Base.metadata.create_all)
        sm = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with sm() as s:
            yield s
    finally:
        await engine.dispose()


async def test_create_persists_item(session):
    repo = _Repo.from_session(session)
    item = await repo.create(_Item(name="alice"), flush=True)
    assert isinstance(item.id, UUID)
    assert item.name == "alice"


async def test_get_by_id_returns_existing(session):
    repo = _Repo.from_session(session)
    created = await repo.create(_Item(name="bob"), flush=True)
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.name == "bob"


async def test_get_by_id_returns_none_when_missing(session):
    repo = _Repo.from_session(session)
    assert await repo.get_by_id(uuid4()) is None


async def test_get_all_returns_every_row(session):
    repo = _Repo.from_session(session)
    await repo.create(_Item(name="a"))
    await repo.create(_Item(name="b"))
    await session.flush()
    rows = await repo.get_all(repo.get_base_statement())
    assert len(rows) == 2


async def test_count(session):
    repo = _Repo.from_session(session)
    for n in ("a", "b", "c"):
        await repo.create(_Item(name=n))
    await session.flush()
    assert await repo.count(repo.get_base_statement()) == 3


async def test_paginate_returns_items_and_total(session):
    repo = _Repo.from_session(session)
    for i in range(15):
        await repo.create(_Item(name=f"n{i:02d}"))
    await session.flush()

    page1, total = await repo.paginate(repo.get_base_statement(), limit=5, page=1)
    assert total == 15
    assert len(page1) == 5

    page2, _ = await repo.paginate(repo.get_base_statement(), limit=5, page=2)
    assert len(page2) == 5
    # Pages don't overlap.
    assert {i.id for i in page1}.isdisjoint({i.id for i in page2})


async def test_update_applies_dict(session):
    repo = _Repo.from_session(session)
    item = await repo.create(_Item(name="old"), flush=True)
    updated = await repo.update(item, update_dict={"name": "new"}, flush=True)
    assert updated.name == "new"


async def test_delete_removes_row(session):
    repo = _Repo.from_session(session)
    item = await repo.create(_Item(name="bye"), flush=True)
    await repo.delete(item, flush=True)
    assert await repo.get_by_id(item.id) is None


async def test_soft_delete_stamps_deleted_at(session):
    from nagara.kit.utils import utc_now

    repo = _Repo.from_session(session)
    item = await repo.create(_Item(name="ghost"), flush=True)
    before = utc_now()
    soft_deleted = await repo.soft_delete(item, flush=True)
    assert soft_deleted.deleted_at is not None
    assert soft_deleted.deleted_at >= before


async def test_soft_delete_excluded_from_default_get_base_statement(session):
    repo = _Repo.from_session(session)
    keep = await repo.create(_Item(name="keep"))
    drop = await repo.create(_Item(name="drop"))
    await session.flush()
    await repo.soft_delete(drop, flush=True)

    visible = await repo.get_all(repo.get_base_statement())
    assert len(visible) == 1
    assert visible[0].id == keep.id


async def test_soft_delete_included_when_include_deleted(session):
    repo = _Repo.from_session(session)
    a = await repo.create(_Item(name="a"))
    await session.flush()
    await repo.soft_delete(a, flush=True)

    all_rows = await repo.get_all(repo.get_base_statement(include_deleted=True))
    assert len(all_rows) == 1


async def test_apply_sorting_orders_results(session):
    from sqlalchemy import select

    repo = _Repo.from_session(session)
    for n in ("c", "a", "b"):
        await repo.create(_Item(name=n))
    await session.flush()

    asc = repo.apply_sorting(select(_Item), [(_SortBy.name, False)])
    result = await session.execute(asc)
    names = [i.name for i in result.scalars().all()]
    assert names == ["a", "b", "c"]

    desc = repo.apply_sorting(select(_Item), [(_SortBy.name, True)])
    result = await session.execute(desc)
    names = [i.name for i in result.scalars().all()]
    assert names == ["c", "b", "a"]


async def test_from_session_returns_repo_bound_to_session(session):
    repo = _Repo.from_session(session)
    assert isinstance(repo, _Repo)
    assert repo.session is session
