"""``nagara`` CLI binary entry point.

Flow::

    1. Resolve API URL (--api-url → NAGARA_API_URL → http://127.0.0.1:8000)
    2. GET /openapi.json
    3. Walk paths; each operation with an ``x-nagara-cli`` block becomes a command
    4. Build argparse with a subparser per command, attach params as flags
    5. Parse argv, dispatch the HTTP call, render the response, print

This file is layer 0 of the design in ``nagara-planning/09-cli-design.md``.
It handles GET operations + query/path parameters + JSON output only.
POST bodies, positional args, flag aliases, Jinja formatters, and auth
come in later layers without breaking this shape.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx

from nagara.cli.formatters import BUILTIN_FORMATTERS, format_json
from nagara.cli.schema import OPENAPI_EXTENSION_KEY, CLICommandSpec

DEFAULT_API_URL = "http://127.0.0.1:8000"
_METHODS = ("get", "post", "put", "patch", "delete")


@dataclass(frozen=True)
class Command:
    """One discovered CLI command + everything needed to dispatch it."""

    segments: tuple[str, ...]  # ("workspace", "ls")
    http_method: str  # "GET"
    path_template: str  # "/workspaces"
    parameters: list[dict[str, Any]]  # raw OpenAPI parameter entries
    spec: CLICommandSpec


# ── Discovery ──────────────────────────────────────────────────────────────


def _fetch_openapi(api_url: str) -> dict[str, Any]:
    """Fetch and parse the server's OpenAPI JSON. Bubbles up httpx errors
    on network failure — let argparse never see the traceback."""
    resp = httpx.get(f"{api_url.rstrip('/')}/openapi.json", timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def discover_commands(openapi: dict[str, Any]) -> list[Command]:
    """Walk the OpenAPI paths and yield every operation tagged with our
    ``x-nagara-cli`` extension."""
    commands: list[Command] = []
    for path, path_item in (openapi.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        # Parameters can live at the path level (shared) and be overridden
        # per-method; merge them once here.
        path_params = list(path_item.get("parameters") or [])
        for method in _METHODS:
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            ext = op.get(OPENAPI_EXTENSION_KEY)
            if not ext:
                continue
            try:
                spec = CLICommandSpec.model_validate(ext)
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(
                    f"warning: ignoring malformed {OPENAPI_EXTENSION_KEY} on "
                    f"{method.upper()} {path}: {exc}\n"
                )
                continue
            params = path_params + list(op.get("parameters") or [])
            commands.append(
                Command(
                    segments=tuple(spec.command.split()),
                    http_method=method.upper(),
                    path_template=path,
                    parameters=params,
                    spec=spec,
                )
            )
    return commands


# ── Parser construction ──────────────────────────────────────────────────


def _flag_name(param_name: str) -> str:
    """``org_id`` → ``--org-id``. Hyphens read better on the command line."""
    return "--" + param_name.replace("_", "-")


def _attach_parameter(parser: argparse.ArgumentParser, param: dict[str, Any]) -> None:
    """Register one OpenAPI parameter as a CLI flag on ``parser``."""
    name = param.get("name")
    if not isinstance(name, str):
        return
    required = bool(param.get("required"))
    description = param.get("description") or ""
    parser.add_argument(
        _flag_name(name),
        dest=name,
        required=required,
        default=None,
        help=description,
    )


def _walk_to_subparser(
    root: argparse._SubParsersAction,
    segments: tuple[str, ...],
    *,
    summary: str | None,
) -> argparse.ArgumentParser:
    """For a command like ``workspace ls``, build nested subparsers so the
    user can type ``nagara workspace --help`` and see ``ls`` listed."""
    parent_sub = root
    parser: argparse.ArgumentParser | None = None
    for i, seg in enumerate(segments):
        # Reuse an existing subparser branch when we've already added it
        # for a sibling command (e.g. two `workspace *` commands).
        existing = parent_sub.choices.get(seg)
        is_leaf = i == len(segments) - 1
        if existing is None:
            parser = parent_sub.add_parser(
                seg,
                help=summary if is_leaf else None,
            )
        else:
            parser = existing
        if not is_leaf:
            # We need another subparsers layer under this segment. argparse
            # disallows multiple ``add_subparsers`` calls per parser, so
            # cache the action on the parser itself.
            sub = getattr(parser, "_nagara_sub", None)
            if sub is None:
                sub = parser.add_subparsers(dest=f"_sub_{i}", required=True)
                parser._nagara_sub = sub  # type: ignore[attr-defined]
            parent_sub = sub
    assert parser is not None
    return parser


def build_parser(commands: list[Command]) -> argparse.ArgumentParser:
    """Assemble the argparse tree from discovered commands."""
    parser = argparse.ArgumentParser(
        prog="nagara",
        description="nagara CLI — dynamically generated from the server's OpenAPI spec.",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("NAGARA_API_URL", DEFAULT_API_URL),
        help=f"Backend URL. Env: NAGARA_API_URL. Default: {DEFAULT_API_URL}.",
    )
    parser.add_argument(
        "--format",
        default=None,
        help="Name of the response formatter. Defaults to what the endpoint declares, else 'json'.",
    )
    root = parser.add_subparsers(dest="_command", required=True)

    for cmd in commands:
        sub = _walk_to_subparser(root, cmd.segments, summary=cmd.spec.summary)
        sub.set_defaults(_nagara_command=cmd)
        for param in cmd.parameters:
            _attach_parameter(sub, param)

    return parser


# ── Dispatch ─────────────────────────────────────────────────────────────


def _build_request(cmd: Command, args: argparse.Namespace) -> tuple[str, dict[str, str]]:
    """Split the resolved args into (URL, query-params) using the
    OpenAPI parameter `in` field as the key."""
    path = cmd.path_template
    query: dict[str, str] = {}
    for param in cmd.parameters:
        name = param.get("name")
        if not isinstance(name, str):
            continue
        value = getattr(args, name, None)
        if value is None:
            continue
        location = param.get("in")
        if location == "path":
            path = path.replace("{" + name + "}", str(value))
        elif location == "query":
            query[name] = str(value)
        # header / cookie params deferred to layer 1.
    return path, query


def _select_formatter(cmd: Command, requested: str | None):
    """Pick the response formatter. Server-declared templates win if the
    user asked for one by name; otherwise fall through to built-ins."""
    name = requested or cmd.spec.default_formatter
    if name in BUILTIN_FORMATTERS:
        return BUILTIN_FORMATTERS[name]
    # Jinja templates come in layer 2 — for now we just print JSON.
    return format_json


def dispatch(cmd: Command, args: argparse.Namespace) -> int:
    """Execute the command. Returns the intended process exit code."""
    path, query = _build_request(cmd, args)
    url = f"{args.api_url.rstrip('/')}{path}"
    try:
        resp = httpx.request(cmd.http_method, url, params=query, timeout=30.0)
    except httpx.HTTPError as exc:
        sys.stderr.write(f"network error: {exc}\n")
        return 2
    try:
        payload: Any = resp.json()
    except ValueError:
        payload = resp.text
    formatter = _select_formatter(cmd, args.format)
    print(formatter(payload))
    return 0 if resp.is_success else 1


# ── Entry point ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]

    # Peel off --api-url before fetching the spec so the URL is known in
    # time for discovery. argparse will also see it below (no harm).
    api_url = os.environ.get("NAGARA_API_URL", DEFAULT_API_URL)
    for i, token in enumerate(argv):
        if token == "--api-url" and i + 1 < len(argv):
            api_url = argv[i + 1]
        elif token.startswith("--api-url="):
            api_url = token.split("=", 1)[1]

    try:
        openapi = _fetch_openapi(api_url)
    except httpx.HTTPError as exc:
        sys.stderr.write(f"failed to fetch {api_url}/openapi.json: {exc}\n")
        return 2

    commands = discover_commands(openapi)
    parser = build_parser(commands)
    args = parser.parse_args(argv)
    cmd = getattr(args, "_nagara_command", None)
    if cmd is None:
        parser.print_help()
        return 1
    return dispatch(cmd, args)


if __name__ == "__main__":
    raise SystemExit(main())
