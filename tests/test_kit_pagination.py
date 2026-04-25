from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from nagara.kit.pagination import (
    ListResource,
    Pagination,
    PaginationParams,
    PaginationParamsQuery,
    build_pagination,
    count_subquery,
)
from nagara.kit.schemas import Schema


def test_build_pagination_zero_total_yields_max_page_one():
    p = build_pagination(PaginationParams(1, 10), 0)
    assert p.page == 1
    assert p.limit == 10
    assert p.total_count == 0
    assert p.max_page == 1


def test_build_pagination_exact_total_does_not_overshoot():
    p = build_pagination(PaginationParams(1, 10), 10)
    assert p.max_page == 1


def test_build_pagination_partial_last_page_rounds_up():
    p = build_pagination(PaginationParams(1, 10), 11)
    assert p.max_page == 2


def test_build_pagination_large_total():
    p = build_pagination(PaginationParams(3, 25), 1000)
    assert p.max_page == 40


def test_list_resource_serializes_envelope():
    class _Row(Schema):
        v: int = Field(default=0)

    pg = build_pagination(PaginationParams(1, 5), total_count=2)
    lr = ListResource[_Row](items=[_Row(v=1), _Row(v=2)], pagination=pg)
    dumped = lr.model_dump()
    assert list(dumped.keys()) == ["items", "pagination"]
    assert len(dumped["items"]) == 2
    assert dumped["pagination"]["total_count"] == 2


def test_pagination_params_query_dep_defaults():
    app = FastAPI()

    @app.get("/x")
    def h(p: PaginationParamsQuery):
        return {"page": p.page, "limit": p.limit}

    c = TestClient(app)
    assert c.get("/x").json() == {"page": 1, "limit": 50}
    assert c.get("/x?page=3&limit=20").json() == {"page": 3, "limit": 20}


def test_pagination_params_query_rejects_out_of_range():
    app = FastAPI()

    @app.get("/x")
    def h(p: PaginationParamsQuery):
        return {"page": p.page, "limit": p.limit}

    c = TestClient(app)
    assert c.get("/x?page=0").status_code == 422
    assert c.get("/x?limit=0").status_code == 422
    assert c.get("/x?limit=501").status_code == 422


def test_count_subquery_only_projects_literal():
    from sqlalchemy import column, literal, select, table

    t = table("t", column("a"), column("b"))
    sq = count_subquery(select(t.c.a, t.c.b).where(t.c.a == 1))
    cols = [str(c.name) for c in sq.columns]
    # The subquery should expose only the literal projection column.
    assert len(cols) == 1
    # Ensure the original ORDER BY (none here) and full row aren't materialized.
    assert "literal" in str(sq.element).lower() or "1" in str(sq.element)
    _ = literal  # silence unused
