"""Repository pattern — keep all DB queries out of services and endpoints.

Convention: every domain has a ``repository.py`` whose ``Repository``
class owns the SQL. Services call repository methods; endpoints call
services. Three layers, narrow seams.

Compose mixins by inheritance order::

    class OrgRepository(
        RepositorySortingMixin[Org, OrgSortProperty],
        RepositorySoftDeletionMixin[Org],
        RepositoryBase[Org],
    ):
        model = Org
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, Self

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped
from sqlalchemy.orm.attributes import flag_modified

from nagara.kit.pagination import count_subquery
from nagara.kit.sorting import Sorting
from nagara.kit.utils import utc_now


class _ModelID[ID](Protocol):
    id: Mapped[ID]


class _ModelDeletedAt(Protocol):
    deleted_at: Mapped[datetime | None]


class RepositoryBase[M: _ModelID[Any]]:
    model: type[M]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @classmethod
    def from_session(cls, session: AsyncSession) -> Self:
        return cls(session)

    def get_base_statement(self) -> Select[tuple[M]]:
        return select(self.model)

    async def get_one(self, statement: Select[tuple[M]]) -> M:
        result = await self.session.execute(statement)
        return result.unique().scalar_one()

    async def get_one_or_none(self, statement: Select[tuple[M]]) -> M | None:
        result = await self.session.execute(statement)
        return result.unique().scalar_one_or_none()

    async def get_all(self, statement: Select[tuple[M]]) -> Sequence[M]:
        result = await self.session.execute(statement)
        return result.scalars().unique().all()

    async def get_by_id(self, id: Any) -> M | None:
        return await self.get_one_or_none(
            self.get_base_statement().where(self.model.id == id)
        )

    async def count(self, statement: Select[tuple[M]]) -> int:
        count_stmt = select(func.count()).select_from(count_subquery(statement))
        return (await self.session.execute(count_stmt)).scalar_one()

    async def paginate(
        self, statement: Select[tuple[M]], *, limit: int, page: int
    ) -> tuple[list[M], int]:
        offset = (page - 1) * limit
        total = await self.count(statement)
        paged = statement.limit(limit).offset(offset)
        items = list((await self.session.execute(paged)).unique().scalars().all())
        return items, total

    async def create(self, object: M, *, flush: bool = False) -> M:
        self.session.add(object)
        if flush:
            await self.session.flush()
        return object

    async def update(
        self,
        object: M,
        *,
        update_dict: dict[str, Any] | None = None,
        flush: bool = False,
    ) -> M:
        if update_dict is not None:
            for attr, value in update_dict.items():
                setattr(object, attr, value)
                # Force SQLAlchemy to include the column in UPDATE even when
                # the new value equals the old — needed for JSON columns
                # whose in-place mutations the ORM can't auto-detect.
                try:
                    flag_modified(object, attr)
                except KeyError:
                    pass
        self.session.add(object)
        if flush:
            await self.session.flush()
        return object

    async def delete(self, object: M, *, flush: bool = False) -> None:
        await self.session.delete(object)
        if flush:
            await self.session.flush()


class RepositorySoftDeletionMixin[M: _ModelDeletedAt]:
    """Adds a ``deleted_at`` filter to ``get_base_statement`` (soft-deleted
    rows excluded by default) and a ``soft_delete`` method that stamps
    ``deleted_at`` instead of issuing DELETE."""

    async def update(  # type: ignore[override]
        self, *args: Any, **kwargs: Any
    ) -> Any: ...  # populated by RepositoryBase via MRO

    def get_base_statement(  # type: ignore[override]
        self, *, include_deleted: bool = False
    ) -> Select[tuple[M]]:
        statement = super().get_base_statement()  # type: ignore[misc]
        if not include_deleted:
            statement = statement.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return statement

    async def soft_delete(self, object: M, *, flush: bool = False) -> M:
        return await self.update(  # type: ignore[no-any-return]
            object, update_dict={"deleted_at": utc_now()}, flush=flush
        )


class RepositorySortingMixin[M, SP: StrEnum]:
    """Apply :data:`Sorting` criteria to a select statement.

    Subclass overrides :meth:`get_sort_clause` to map each enum member to
    a SQL column expression. Default implementation introspects ``model``
    for an attribute matching the enum value name.
    """

    def get_sort_clause(self, sort: SP) -> Any:
        column = getattr(self.model, sort.value)  # type: ignore[attr-defined]
        return column

    def apply_sorting(
        self, statement: Select[tuple[M]], sorting: Sequence[Sorting[SP]]
    ) -> Select[tuple[M]]:
        for sort_property, descending in sorting:
            clause = self.get_sort_clause(sort_property)
            statement = statement.order_by(desc(clause) if descending else asc(clause))
        return statement
