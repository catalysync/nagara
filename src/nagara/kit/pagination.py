"""Pagination primitives shared across list endpoints.

Endpoints accept :data:`PaginationParamsQuery` as a dependency and call
:func:`paginate` to fetch the page + total count in one round-trip-ish.
The response is a :class:`ListResource` so every list endpoint emits the
same ``{items, pagination}`` envelope on the wire.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Annotated, Any, NamedTuple

from fastapi import Depends, Query
from pydantic import Field
from sqlalchemy import Select, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from nagara.kit.schemas import Schema


class PaginationParams(NamedTuple):
    page: int
    limit: int


def _pagination_params_dep(
    page: int = Query(1, ge=1, description="Page number, starting at 1."),
    limit: int = Query(50, ge=1, le=500, description="Items per page (1-500)."),
) -> PaginationParams:
    return PaginationParams(page=page, limit=limit)


PaginationParamsQuery = Annotated[PaginationParams, Depends(_pagination_params_dep)]


class Pagination(Schema):
    page: int = Field(description="Current page number (1-indexed).")
    limit: int = Field(description="Items per page.")
    total_count: int = Field(description="Total items across all pages.")
    max_page: int = Field(description="Last page number (1 when empty).")


class ListResource[T](Schema):
    """``{items, pagination}`` envelope for every list endpoint."""

    items: list[T] = Field(description="Page of results.")
    pagination: Pagination


def count_subquery(statement: Select[Any]) -> Subquery:
    """Build a count-safe subquery that doesn't re-materialize every
    mapped column. ``Select(Model).subquery()`` ignores ``deferred=True``
    and projects the whole row — wasteful for COUNT(*) where we only
    need cardinality."""
    return statement.with_only_columns(literal(1)).order_by(None).subquery()


async def paginate(
    session: AsyncSession,
    statement: Select[Any],
    *,
    pagination: PaginationParams,
) -> tuple[Sequence[Any], int]:
    """Run ``statement`` with offset/limit + a separate COUNT for total.

    Returns ``(items, total_count)``. Build the wire envelope at the
    endpoint layer with :class:`ListResource` + :class:`Pagination`.
    """
    page, limit = pagination
    offset = limit * (page - 1)

    count_stmt = select(func.count()).select_from(count_subquery(statement))
    total = (await session.execute(count_stmt)).scalar_one()

    paged = statement.offset(offset).limit(limit)
    items = list((await session.execute(paged)).unique().scalars().all())
    return items, total


def build_pagination(
    pagination: PaginationParams, total_count: int
) -> Pagination:
    """Convenience: turn ``(page, limit, total_count)`` into a populated
    :class:`Pagination` with ``max_page`` computed."""
    page, limit = pagination
    max_page = max(1, math.ceil(total_count / limit)) if total_count else 1
    return Pagination(page=page, limit=limit, total_count=total_count, max_page=max_page)
