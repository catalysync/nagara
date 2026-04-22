#!/usr/bin/env bash
# Run the test suite against real Postgres + Redis from docker-compose.
# Brings the services up, waits for them, runs pytest, tears down on exit.
set -euo pipefail

cd "$(dirname "$0")/.."

cleanup() {
    docker compose down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose up -d postgres redis

# Wait for Postgres to actually accept connections — healthcheck states don't
# surface fast enough to rely on ``depends_on`` from the test runner.
echo "waiting for postgres..."
until docker compose exec -T postgres pg_isready -U "${NAGARA_POSTGRES_USER:-nagara}" >/dev/null 2>&1; do
    sleep 0.5
done

NAGARA_POSTGRES_HOST=127.0.0.1 \
NAGARA_POSTGRES_PORT=5432 \
NAGARA_POSTGRES_USER="${NAGARA_POSTGRES_USER:-nagara}" \
NAGARA_POSTGRES_PWD="${NAGARA_POSTGRES_PWD:-nagara}" \
NAGARA_POSTGRES_DB="${NAGARA_POSTGRES_DB:-nagara}" \
    uv run pytest "$@"
