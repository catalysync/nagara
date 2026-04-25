"""``CLIRouter`` — FastAPI router that accepts CLI-spec kwargs on decorators.

Keeps the view code clean. Instead of::

    @router.get("/workspaces", openapi_extra={"x-nagara-cli": {
        "command": "workspace ls",
        "summary": "List workspaces",
        ...
    }})
    def list_workspaces(...): ...

write::

    @router.get("/workspaces", cli_command="workspace ls",
                cli_summary="List workspaces")
    def list_workspaces(...): ...

Each verb decorator strips the ``cli_*`` kwargs, validates them against
:class:`CLICommandSpec`, and merges the rendered ``x-nagara-cli`` block
into whatever ``openapi_extra`` the caller passed.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from nagara.cli.schema import CLICommandSpec, build_extension

# Decorator kwargs that configure the CLI extension. Anything else passes
# through to APIRouter unchanged.
_CLI_KWARGS = frozenset(
    {
        "cli_command",
        "cli_summary",
        "cli_description",
        "cli_positional",
        "cli_flag_aliases",
        "cli_formatters",
        "cli_default_formatter",
    }
)


def _pull_cli_into_openapi_extra(kwargs: dict[str, Any]) -> None:
    """Mutate ``kwargs`` in place: strip any ``cli_*`` keys, build the
    ``x-nagara-cli`` extension from them, merge into ``openapi_extra``."""
    pulled = {k[len("cli_") :]: kwargs.pop(k) for k in list(kwargs) if k in _CLI_KWARGS}
    if "command" not in pulled:
        # No cli_command → caller isn't opting in. Nothing to inject.
        return
    spec = CLICommandSpec(**pulled)
    existing = kwargs.get("openapi_extra") or {}
    kwargs["openapi_extra"] = {**existing, **build_extension(spec)}


class CLIRouter(APIRouter):
    """APIRouter that turns ``cli_*`` decorator kwargs into an
    ``x-nagara-cli`` OpenAPI extension on the generated spec.

    FastAPI's ``APIRouter.get/post/put/delete/patch`` have strict
    signatures and don't forward unknown kwargs down to ``add_api_route``,
    so we override each verb method to strip the CLI kwargs before
    delegating.
    """

    def get(self, path: str, **kwargs: Any):  # type: ignore[override]
        _pull_cli_into_openapi_extra(kwargs)
        return super().get(path, **kwargs)

    def post(self, path: str, **kwargs: Any):  # type: ignore[override]
        _pull_cli_into_openapi_extra(kwargs)
        return super().post(path, **kwargs)

    def put(self, path: str, **kwargs: Any):  # type: ignore[override]
        _pull_cli_into_openapi_extra(kwargs)
        return super().put(path, **kwargs)

    def patch(self, path: str, **kwargs: Any):  # type: ignore[override]
        _pull_cli_into_openapi_extra(kwargs)
        return super().patch(path, **kwargs)

    def delete(self, path: str, **kwargs: Any):  # type: ignore[override]
        _pull_cli_into_openapi_extra(kwargs)
        return super().delete(path, **kwargs)
