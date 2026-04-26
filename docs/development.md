# Development

How to get a working local copy and start contributing.

## Prerequisites

- Python 3.14+
- [`uv`](https://github.com/astral-sh/uv)
- [`just`](https://github.com/casey/just) — task runner
- [Docker](https://docs.docker.com/get-docker/) + Compose v2
- Node.js 22+ and pnpm 9+ (only if you're touching the frontend)

## One-shot bootstrap

```bash
just bootstrap
```

That syncs Python deps, brings up Postgres and Redis via Docker Compose, and
leaves the database ready to accept connections. The justfile is the
authoritative command reference — `just --list` to see everything.

## Day-to-day

```bash
just dev         # uvicorn with --reload on 127.0.0.1:8000
just test        # pytest
just check       # ruff format --check, ruff check, ty, pytest — same as CI
just migrate     # alembic upgrade head
just makemigration "add X"   # autogenerate from model diffs
```

For the frontend (if applicable):

```bash
pnpm -C frontend dev      # next dev --turbopack
pnpm -C frontend test
pnpm -C frontend generate:client   # regenerate TS client from live OpenAPI
```

## Configuration

The app reads config from multiple sources (priority, highest first):

1. `Settings(...)` init kwargs (test-only)
2. Environment variables (`NAGARA_*`)
3. `.env` / `.env.test` / `.env.staging` files
4. Active profile in `~/.config/nagara/profiles.toml`
5. `~/.config/nagara/config.toml`
6. `pyproject.toml` `[tool.nagara]` table
7. Field defaults

For local dev: copy `.env.example` to `.env` and fill in what you need. Most
defaults are already sensible.

## Database + migrations

- Compose brings up Postgres on port 5432 with user/db both `nagara`.
- `just migrate` runs `alembic upgrade head`.
- `just makemigration "message"` autogenerates a migration from model diffs.
- `just downgrade` rolls back one revision.
- `just db-reset` drops + recreates the local database. **Destructive, dev only.**

Migrations have post-write hooks wired in `alembic.ini` — new revision files
get formatted by ruff automatically.

## Tests

The suite is mostly hermetic — settings/middleware/routing/exception/kit
tests run with no external services. The rate-limit and postgres-preflight
tests need real Redis and Postgres respectively (`just bootstrap` brings
them up).

```bash
just test                         # full suite
uv run pytest tests/test_foo.py   # single file
uv run pytest -k "slug"           # match by name
uv run pytest -x                  # stop at first failure
```

## Code quality

Run `just check` before pushing. CI runs the same thing:

- `ruff format --check` — formatting
- `ruff check` — lint (with `UP`, `B`, `SIM`, `I` rules enabled)
- `ty check` — type-check
- `pytest` — tests

Pre-commit hooks are available; install once with `uv run pre-commit install`.

## Docker + Helm

The production image builds from the repo-root `Dockerfile` (multi-stage,
uv-driven, non-root runtime). To try the Helm chart locally:

```bash
helm lint deploy/helm/nagara-core
helm template deploy/helm/nagara-core \
  --set secrets.NAGARA_SECRET_KEY=dev \
  --set secrets.NAGARA_POSTGRES_PWD=dev
```

See [deployment.md](./deployment.md) for the full deploy path.

## Commit conventions

See [CONTRIBUTING.md](../CONTRIBUTING.md#commit-style) — lowercase, ≤30
chars, no prefix scopes, no AI-attribution footers.

## Project structure

```
src/nagara/            backend package (config, middleware, routing, kit, …)
frontend/              Next.js 15 + Tailwind v4 scaffold
alembic/               Alembic migration chain
deploy/helm/           Helm chart for k8s deploy
docs/                  This directory
tests/                 pytest suite
```

## Getting help

- Open an issue on GitHub.
- Read [`CLAUDE.md`](../CLAUDE.md) for module conventions and the kit/ split.
