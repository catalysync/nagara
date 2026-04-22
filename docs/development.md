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

Tests run against in-memory SQLite for model-level and endpoint-level cases
(see `tests/conftest.py`). Anything that exercises Postgres-only behavior
(jsonb operators, partial indexes, `inet` columns) needs a separate fixture
pointing at the live Postgres — add those alongside the relevant module.

```bash
just test                         # full suite
uv run pytest tests/test_foo.py   # single file
uv run pytest -k "slug"           # match by name
uv run pytest -x                  # stop at first failure
```

The suite currently runs in <10s. Keep it that way by favoring SQLite-backed
fixtures where possible and opting into Postgres only when you need
Postgres-specific SQL.

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

- Lowercase, ≤50 characters
- Conventional Commit prefix (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`,
  `test:`, `perf:`, `ci:`, `build:`) is optional but strongly encouraged —
  `release-please` uses it to auto-generate release notes and bump versions
- No AI-attribution footers (`Co-Authored-By: Claude …` etc)
- No trailing period on the subject line

Examples:
- `feat: add outbox pattern`
- `fix: dedupe billing webhooks`
- `add org model`  (acceptable — unprefixed, short)
- ~~`feat: add a whole bunch of stuff for the outbox and billing`~~  (too long)

## Project structure

```
src/nagara/            backend package (API, models, auth, outbox, …)
frontend/              Next.js 15 + Tailwind v4 + mizu consumer
alembic/               Alembic migration chain
deploy/helm/           Helm chart for k8s deploy
docs/                  This directory
tests/                 pytest suite
```

## Getting help

- Open an issue on GitHub.
- Check the planning docs under [`nagara-planning/`](https://github.com/catalysync/nagara-planning) for architecture background.
