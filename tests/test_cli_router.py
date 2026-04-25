"""CLIRouter injects `x-nagara-cli` into the generated OpenAPI spec."""

from __future__ import annotations

from fastapi import FastAPI

from nagara.cli import CLIRouter
from nagara.cli.schema import OPENAPI_EXTENSION_KEY


def test_cli_router_injects_extension_when_cli_command_given():
    router = CLIRouter()

    @router.get(
        "/widgets",
        cli_command="widget ls",
        cli_summary="List widgets",
    )
    def _list_widgets() -> dict:
        return {"items": []}

    app = FastAPI()
    app.include_router(router)
    spec = app.openapi()

    op = spec["paths"]["/widgets"]["get"]
    assert OPENAPI_EXTENSION_KEY in op
    cli_block = op[OPENAPI_EXTENSION_KEY]
    assert cli_block["command"] == "widget ls"
    assert cli_block["summary"] == "List widgets"


def test_cli_router_omits_extension_when_cli_command_absent():
    """Endpoints without a cli_command shouldn't grow a CLI block."""
    router = CLIRouter()

    @router.get("/plain")
    def _plain() -> dict:
        return {}

    app = FastAPI()
    app.include_router(router)
    op = app.openapi()["paths"]["/plain"]["get"]
    assert OPENAPI_EXTENSION_KEY not in op


def test_cli_router_preserves_existing_openapi_extra():
    """Merge rather than clobber — callers can set their own openapi_extra
    for non-CLI metadata without losing the CLI injection."""
    router = CLIRouter()

    @router.get(
        "/stuff",
        openapi_extra={"x-some-other-ext": {"foo": "bar"}},
        cli_command="stuff ls",
    )
    def _stuff() -> dict:
        return {}

    app = FastAPI()
    app.include_router(router)
    op = app.openapi()["paths"]["/stuff"]["get"]
    assert op["x-some-other-ext"]["foo"] == "bar"
    assert op[OPENAPI_EXTENSION_KEY]["command"] == "stuff ls"
