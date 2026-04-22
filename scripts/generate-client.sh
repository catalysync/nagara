#!/usr/bin/env bash
# Regenerate the frontend's TypeScript client from the backend's OpenAPI spec.
#
# Uses the import-and-dump pattern: loads the FastAPI app in-process and calls
# ``app.openapi()`` rather than hitting ``/openapi.json`` on a running server.
# No Postgres, no port, no race — works in CI and locally.
set -euo pipefail

cd "$(dirname "$0")/.."

uv run python -c "import json; from nagara.main import app; print(json.dumps(app.openapi()))" \
    > frontend/openapi.json

pnpm --filter frontend generate:client
