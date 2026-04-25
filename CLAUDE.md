# nagara — Development Guide

FastAPI / SQLAlchemy / Postgres backend. Single-process today; designed
to scale to multi-replica behind a load balancer.

## Quick commands

```bash
just dev                  # Start API on http://127.0.0.1:8000 with reload
just test                 # Run pytest
just lint                 # ruff check --fix
just typecheck            # ty
docker compose up -d      # Postgres + Redis + MinIO + bucket setup

uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

## Module layout

```
src/nagara/
├── main.py            FastAPI factory + health endpoints + handler wiring
├── config.py          Layered settings (env > .env > TOML > defaults)
├── exceptions.py      Typed NagaraError envelope (BadRequest/NotFound/...)
├── routing.py         APIRouter with autocommit + APITag filter
├── middleware.py      Request-ID + Content-Size middleware + log filter
├── logging.py         structlog + dev/prod renderers
├── lifespan.py        @on_startup / @on_shutdown registries
├── rate_limit.py      slowapi limiter (Redis-backed)
├── sentry.py          configure_sentry() (no-op when DSN unset)
├── json_types.py      JSON shape aliases (JSONDict / JSONAny)
├── db/                SQLAlchemy declarative base + session
└── kit/               Reusable building blocks (every domain imports from here)
    ├── utils.py             utc_now, generate_uuid
    ├── schemas.py           Schema, IDSchema, TimestampedSchema, EmptyStrToNone
    ├── pagination.py        PaginationParams, paginate(), ListResource[T]
    ├── sorting.py           parse_sorting() with structured ValidationFailed
    ├── repository/          RepositoryBase + soft-delete + sorting mixins
    ├── pubsub.py            In-process async PubSub (SSE backbone)
    ├── sse.py               format_event / progress / complete / error
    ├── paths.py             safe_join — path traversal guard
    └── redis.py             Async Redis client factory with retry + client_name
```

## Domain module convention

Every domain module follows this shape:

```
src/nagara/{module}/
├── __init__.py
├── model.py        SQLAlchemy ORM
├── schemas.py      Pydantic request/response schemas
├── repository.py   ALL DB queries live here
├── service.py      Business logic; calls repositories
├── routes.py       FastAPI route handlers; calls services
└── deps.py         Auth + other route dependencies (when needed)
```

Aggregator: `nagara/api.py` imports every router and mounts on `/v1`.

## Repository pattern (rule, not suggestion)

**ALL database queries MUST be in repository files.** Services call
repositories; routes call services. No raw SQL or `select()` calls in
service or route files.

```python
# {module}/repository.py
from nagara.kit.repository import RepositoryBase, RepositorySortingMixin

class OrgRepository(
    RepositorySortingMixin[Org, OrgSortProperty],
    RepositoryBase[Org],
):
    model = Org

    def get_readable_statement(self, user: User) -> Select[tuple[Org]]:
        return self.get_base_statement().where(
            Org.id.in_(
                select(Membership.org_id).where(Membership.user_id == user.id)
            )
        )

    async def get_by_slug(self, slug: str) -> Org | None:
        return await self.get_one_or_none(
            self.get_base_statement().where(Org.slug == slug)
        )
```

## Session — never call `session.commit()` in service code

The custom `APIRoute` in `nagara.routing` commits the first
`AsyncSession` argument after the handler returns. Each domain wires its
own `get_session` dep that should also commit on success / roll back on
exception (idempotent — two commits is a no-op in SQLAlchemy).

```python
async def create(self, session: AsyncSession, payload) -> Resource:
    repo = ResourceRepository.from_session(session)
    return await repo.create(Resource(**payload.model_dump()))
    # NO session.commit() — happens automatically via the route wrapper
    # (and the dep, if your domain wires one)
```

Use `await session.flush()` if you need the row's generated id before
the response goes out.

## Endpoint pattern

```python
from nagara.routing import APIRouter, APITag
from nagara.kit.pagination import ListResource, PaginationParamsQuery, build_pagination

router = APIRouter(prefix="/orgs", tags=[APITag.public, "orgs"])

@router.get("/", response_model=ListResource[OrgSchema], responses={
    403: {"model": Forbidden.schema()},
})
async def list_orgs(
    user: AuthedUser,
    pagination: PaginationParamsQuery,
    session: AsyncSession = Depends(get_session),
) -> ListResource[OrgSchema]:
    items, total = await org_service.list(session, user, pagination=pagination)
    return ListResource(items=items, pagination=build_pagination(pagination, total))
```

`tags=[APITag.public, ...]` makes the route show up in the OpenAPI spec.
`tags=[APITag.internal, ...]` hides it in production but shows in dev. No
tag = hidden everywhere (admin-only).

## Errors

Raise typed exceptions from `nagara.exceptions`; the handler turns them
into the wire envelope:

```python
raise NotFound("organization not found", extra={"org_id": str(org_id)})
# → 404 {"error": "not_found", "detail": "...", "request_id": "...", "extra": {...}}
```

For field-level validation failures from service code:

```python
raise ValidationFailed(errors=[
    {"loc": ("body", "email"), "msg": "already taken", "type": "value_error.unique"}
])
# → 422 with errors[] in the same shape Pydantic emits for body validation
```

To make the error a typed discriminated union in the generated TS client,
declare it on the route with `responses={cls.status_code: {"model": cls.schema()}}`.

## Pagination

Offset/limit by default. Cursor pagination reserved for high-cardinality
log/event endpoints (not built yet).

```python
@router.get("/", response_model=ListResource[X])
async def list_x(pagination: PaginationParamsQuery, session = Depends(get_session)):
    items, total = await paginate(session, statement, pagination=pagination)
    return ListResource(items=items, pagination=build_pagination(pagination, total))
```

## Logging

`structlog` + dev/prod renderers (configured at module import in `main.py`).
Bind contextvars early in a request and they auto-merge into every log:

```python
import structlog
structlog.contextvars.bind_contextvars(user_id=str(user.id), org_id=str(org.id))
log.info("created order", order_id=str(order.id), amount_cents=order.amount)
```

Don't use `logging.getLogger(...)` inside hot paths — use
`structlog.get_logger()` for keyword-args ergonomics. Both are routed
through the same pipeline.

## Tests

Tests live in `tests/` with the per-worker DB pattern. Pytest fixtures
wrap every test in a transaction that rolls back at teardown — no
manual cleanup needed.

```bash
just test                       # full suite
just coverage                   # branch coverage report
uv run pytest tests/test_<module>.py -k <name>  # one test
```

## Adding a new domain module

1. `mkdir src/nagara/{module}` with `__init__.py`, `model.py`, `schemas.py`, `repository.py`, `service.py`, `routes.py`
2. Define ORM model in `model.py` — subclass `Base` from `nagara.db`, use `UUIDPrimaryKeyMixin` + `TimestampedMixin` from `nagara.db.mixins`
3. Generate migration: `uv run alembic revision --autogenerate -m "add {module} table"`
4. Define Pydantic schemas in `schemas.py` — subclass `Schema` / `IDSchema` / `TimestampedSchema` from `nagara.kit.schemas`
5. Write repository in `repository.py` — subclass `RepositoryBase[Model]` from `nagara.kit.repository`
6. Write service in `service.py` — singleton instance at module bottom: `{module}_service = {Module}Service()`
7. Write routes in `routes.py` — `from nagara.routing import APIRouter, APITag`
8. Register router in `nagara/api.py`

## Things we deliberately don't do

- **Workers** — no Dramatiq/Celery/Arq yet. All work runs in the request. Add when first scheduled job lands.
- **Distributed locks** — single-process, no need. Add when multi-replica.
- **OAuth providers** — email/password JWT only. Add per-provider when needed.
- **Cookie sessions** — bearer-token auth, no CSRF surface.
- **PostHog / Logfire** — premature. Stdlib logs cover today.
- **Schema-per-tenant** — single shared DB with `org_id` columns + auth-aware queries.
