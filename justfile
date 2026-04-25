# Common dev commands. Install `just` (https://github.com/casey/just) then
# run e.g. `just dev`, `just test`, `just check`.

set shell := ["bash", "-cu"]
set dotenv-load := false

# Default — list available recipes.
default:
    @just --list --unsorted

# ── Setup ───────────────────────────────────────────────────────────────

# Sync deps + bring up local services. One-shot bootstrap from a fresh clone.
bootstrap:
    uv sync --all-groups
    docker compose up -d postgres redis
    @echo ""
    @echo "Bootstrapped. Start the app with: just dev"

# ── Run ─────────────────────────────────────────────────────────────────

# Run the API with hot reload.
dev:
    uv run uvicorn nagara.main:app --reload --host 127.0.0.1 --port 8000

# Run the API exactly the way the Docker image runs it (no reload).
serve:
    uv run uvicorn nagara.main:app --host 0.0.0.0 --port 8000

# ── Quality ─────────────────────────────────────────────────────────────

# Format Python sources.
format:
    uv run ruff format

# Lint (with auto-fix where possible).
lint:
    uv run ruff check --fix

# Type-check.
typecheck:
    uv run ty check

# Run the tests against the currently-configured Postgres (expects it running).
test:
    uv run pytest

# Run the suite with branch coverage; HTML at htmlcov/index.html.
coverage:
    uv run pytest --cov --cov-report=term-missing --cov-report=html

# Bring up postgres + redis via compose, run the suite, tear down.
test-integration:
    ./scripts/test-integration.sh

# Regenerate the TypeScript client from the backend's OpenAPI spec (no server needed).
generate-client:
    ./scripts/generate-client.sh

# Print every Settings field + default as TOML. Pipe to a file for a starting config.
config-dump:
    uv run python scripts/config-dump.py

# Rewrite docs/config-reference.md from the Settings model.
config-docs:
    uv run python scripts/generate-config-docs.py

# All checks — what CI runs. Run before pushing.
check:
    uv run ruff format --check
    uv run ruff check
    uv run ty check
    uv run pytest

# ── Database ────────────────────────────────────────────────────────────

# Apply all pending migrations against the configured database.
migrate:
    uv run alembic upgrade head

# Generate a new auto-detected migration. Pass a description: `just makemigration "add users"`.
makemigration desc:
    uv run alembic revision --autogenerate -m "{{desc}}"

# Roll the database back one revision.
downgrade:
    uv run alembic downgrade -1

# Drop + recreate the database. DESTRUCTIVE — local dev only.
db-reset:
    docker compose down postgres
    docker volume rm nagara_postgres_data || true
    docker compose up -d postgres
    @echo "Waiting for postgres…" && sleep 3
    just migrate

# ── Docker ──────────────────────────────────────────────────────────────

# Build the production-ish image locally.
docker-build:
    docker build -t nagara:local .

# Bring up the full app stack in containers.
docker-up:
    docker compose --profile app up -d --build

# Stop and clean up the local stack.
docker-down:
    docker compose --profile app down
