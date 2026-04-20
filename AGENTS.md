# AGENTS.md

Conventions, dev loop, and project layout for anyone (human or AI) contributing to this repo.

## Dev loop

Install / sync deps:
```bash
uv sync --all-groups
```

Run the app:
```bash
uv run uvicorn nagara.main:app --reload
```

Run the full check suite:
```bash
uv run ruff format --check && uv run ruff check && uv run pytest
```

Auto-fix style:
```bash
uv run ruff format
uv run ruff check --fix
```

## Python

- Target Python version: `>=3.14` (pinned in `.python-version`)
- Type hints are required on public APIs. Use modern syntax: `int | None`, `list[str]`, `dict[str, int]`.
- No `from typing import Optional, List, Dict` — use built-in generics.
- Prefer `from __future__ import annotations` only when needed (e.g. forward refs).

## Style

- Configured via `[tool.ruff]` in `pyproject.toml`.
- Line length: 100.
- Rule sets enabled: E, W, F, I, B, UP, SIM.
- Formatter does the work; don't argue with it.

## Testing

- Pytest with plain `assert` statements.
- Tests live in `tests/`, files are `test_*.py`, functions are `test_*`.
- Run with `uv run pytest`.
- Every new endpoint should have at least one test.

## Commits

- Lowercase only.
- Subject ≤30 characters.
- No prefixes (`feat:`, `fix:`, etc.).
- No co-authors or AI attribution trailers.
- Examples: `add ty`, `wire auth deps`, `fix health route`, `init workspace module`.

## Layout

```
nagara/
├── pyproject.toml         # project metadata, deps, tool configs
├── uv.lock                # locked dep versions
├── .python-version        # pinned Python version for uv
├── .github/workflows/     # CI
├── src/nagara/            # application package
│   ├── __init__.py
│   └── main.py            # FastAPI app entrypoint
└── tests/                 # pytest tests
```

## Contributing

Open a PR against `main`. CI runs format check + lint + tests on every push and PR.
