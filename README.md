# nagara

> Your operating system for data.

[![CI](https://github.com/catalysync/nagara/actions/workflows/ci.yml/badge.svg)](https://github.com/catalysync/nagara/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)

## Quickstart

Requires `uv`, `docker`, `just`.

```bash
just bootstrap          # uv sync + bring up postgres + redis + minio
cp .env.example .env    # edit NAGARA_SECRET_KEY at minimum
just dev                # API on http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000/docs` for the interactive OpenAPI playground,
`/health/live` and `/health/ready` for the Kubernetes-ready probes.

## Stack

- **Python 3.14** with [uv](https://github.com/astral-sh/uv) for env management
- **FastAPI** + custom `APIRouter` (auto-commit + OpenAPI tag filtering)
- **PostgreSQL** via SQLAlchemy 2 + asyncpg (async) and psycopg2 (sync, for migrations)
- **Redis** for rate limiting and (eventually) cache + queue
- **MinIO** in dev, S3-compatible in prod, for file storage
- **Alembic** for migrations (datetime-prefixed, autoformatted)
- **structlog** with dev/prod renderers (pretty console / JSON)
- **Sentry** for error reporting, **slowapi** for rate limiting
- **Pytest** with coverage tooling (`just coverage`)

## Module map

```
src/nagara/
├── main.py            FastAPI factory + health endpoints
├── config.py          Layered settings (env > .env > TOML > defaults)
├── exceptions.py      Typed NagaraError envelope
├── routing.py         Custom APIRouter (autocommit + APITag.public/internal)
├── middleware.py      Request-ID, content-size, request-cancel, multipart, etc.
├── logging.py         structlog + dev/prod renderers
├── lifespan.py        @on_startup / @on_shutdown registries
├── rate_limit.py      slowapi limiter (Redis-backed)
├── sentry.py          configure_sentry() (no-op when DSN unset)
├── db/                SQLAlchemy declarative base + session
└── kit/               Reusable building blocks for domain modules
    ├── utils, schemas, pagination, sorting, repository
    ├── pubsub, sse, paths, redis, compression
```

See [`CLAUDE.md`](./CLAUDE.md) for the full development guide and module conventions.

## Development

```bash
just test             # pytest
just coverage         # pytest + branch coverage report
just lint             # ruff check --fix
just typecheck        # ty
just check            # everything CI runs
```

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md). Issues and PRs welcome —
please read [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) first.

## Security

Found a vulnerability? See [`SECURITY.md`](./SECURITY.md) for the
disclosure process. Please don't open public issues for security reports.

## License

Apache-2.0 — see [`LICENSE`](./LICENSE).
