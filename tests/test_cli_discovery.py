"""End-to-end: discover commands from a mock OpenAPI spec, dispatch over
a mocked httpx, confirm URL + query are built correctly."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from nagara.cli.main import build_parser, discover_commands, dispatch
from nagara.cli.schema import OPENAPI_EXTENSION_KEY

_SAMPLE_OPENAPI = {
    "paths": {
        "/workspaces": {
            "get": {
                "parameters": [
                    {"name": "org_id", "in": "query", "required": True, "description": "Org id"},
                ],
                OPENAPI_EXTENSION_KEY: {
                    "command": "workspace ls",
                    "summary": "List workspaces",
                },
            }
        },
        "/orgs/{org_id}": {
            "get": {
                "parameters": [
                    {"name": "org_id", "in": "path", "required": True},
                ],
                OPENAPI_EXTENSION_KEY: {
                    "command": "org show",
                },
            }
        },
        "/boring": {"get": {"parameters": []}},  # no extension → ignored
    }
}


def test_discover_finds_commands_with_extension_only():
    cmds = discover_commands(_SAMPLE_OPENAPI)
    names = sorted(" ".join(c.segments) for c in cmds)
    assert names == ["org show", "workspace ls"]


def test_discover_ignores_operations_without_extension():
    cmds = discover_commands(_SAMPLE_OPENAPI)
    assert all(c.path_template != "/boring" for c in cmds)


def test_build_parser_nests_subparsers_per_segment():
    cmds = discover_commands(_SAMPLE_OPENAPI)
    parser = build_parser(cmds)
    # ``nagara workspace ls --org-id X`` should parse.
    args = parser.parse_args(["workspace", "ls", "--org-id", "abc"])
    assert args.org_id == "abc"
    assert args._nagara_command.http_method == "GET"


def test_dispatch_builds_correct_url_and_query():
    cmds = discover_commands(_SAMPLE_OPENAPI)
    parser = build_parser(cmds)
    args = parser.parse_args(
        ["--api-url", "http://example.test", "workspace", "ls", "--org-id", "abc"]
    )

    response = MagicMock()
    response.json.return_value = [{"id": 1}]
    response.is_success = True

    with patch("nagara.cli.main.httpx.request", return_value=response) as req:
        exit_code = dispatch(args._nagara_command, args)

    req.assert_called_once()
    kwargs = req.call_args.kwargs
    positional = req.call_args.args
    # called as httpx.request("GET", url, params=..., timeout=...)
    assert positional[0] == "GET"
    assert positional[1] == "http://example.test/workspaces"
    assert kwargs["params"] == {"org_id": "abc"}
    assert exit_code == 0


def test_dispatch_substitutes_path_parameters():
    cmds = discover_commands(_SAMPLE_OPENAPI)
    parser = build_parser(cmds)
    args = parser.parse_args(["--api-url", "http://example.test", "org", "show", "--org-id", "xyz"])

    response = MagicMock()
    response.json.return_value = {"id": "xyz"}
    response.is_success = True

    with patch("nagara.cli.main.httpx.request", return_value=response) as req:
        dispatch(args._nagara_command, args)

    # The path template {org_id} should have been replaced inline.
    assert req.call_args.args[1] == "http://example.test/orgs/xyz"
    # Path params must not leak into the query string.
    assert req.call_args.kwargs["params"] == {}
