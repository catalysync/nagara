# Contributing to nagara

Thank you for considering a contribution. nagara is in active early
development; the foundation is intentionally small so contributors can
learn the whole codebase in an afternoon.

## Quick dev loop

```bash
just bootstrap        # uv sync + start postgres/redis/minio
cp .env.example .env  # set NAGARA_SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_urlsafe(64))")
just dev              # API on http://127.0.0.1:8000
```

Inside the codespace or any local Linux/macOS:
```bash
just test             # full test suite
just coverage         # with branch coverage at htmlcov/index.html
just lint             # ruff format + check --fix
just typecheck        # ty
just check            # everything CI runs (lint + format + types + tests)
```

## Module conventions

See [`CLAUDE.md`](./CLAUDE.md) — it documents the repository pattern,
service layer, route structure, and the kit/ split. New domain modules
follow `model.py / schemas.py / repository.py / service.py / routes.py`.

## Commit style

- Lowercase, present tense, ≤ 30 chars in the title (e.g., `add rate limiting`)
- No prefix scopes (`feat:` / `fix:` / etc.)
- Each commit a focused logical unit — `git rebase -i --autosquash` welcome
- Body explains *why* when non-obvious

## Pull requests

1. Branch from `main` (or the closest stacked branch) — `git checkout -b feat/<short-name>`
2. Run `just check` locally before pushing
3. Add tests for new code in `tests/test_<module>.py`
4. Open a PR with a description that covers what changed and why
5. Be patient — solo maintainer right now

## Bug reports

Open an issue with:
- nagara version + git SHA
- Python version (`python -V`)
- Minimal reproduction
- Stack trace if applicable
- Expected vs actual behavior

## Feature requests

Open a discussion first. Most feature ideas live in
[`nagara-planning/`](https://github.com/catalysync/nagara-planning) — if
your idea isn't there, the discussion is the right place to start.

## Code of conduct

By participating you agree to abide by the
[Code of Conduct](./CODE_OF_CONDUCT.md).
