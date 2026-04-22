"""Schema for the ``x-nagara-cli`` OpenAPI extension.

Every endpoint that wants a CLI command embeds a block matching
:class:`CLICommandSpec` under ``x-nagara-cli`` in its OpenAPI entry.
The CLI binary reads the block at startup to build its argparse parser.

New keys here are additive — old CLI builds tolerate unknown fields, old
servers simply don't emit keys newer builds know about. This is the one
contract between server and CLI.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

OPENAPI_EXTENSION_KEY = "x-nagara-cli"


class CLICommandSpec(BaseModel):
    """CLI metadata for a single API endpoint.

    The ``command`` value is the space-separated path a user types:
    ``workspace ls``, ``org create``. The CLI turns each segment into a
    nested argparse subparser so `nagara workspace --help` reveals every
    workspace-scoped command.
    """

    # extra="allow" so the server can ship forward-compatible keys that
    # older CLI builds silently ignore.
    model_config = ConfigDict(extra="allow")

    command: str = Field(
        description="Space-separated command name. Segments become nested subparsers.",
    )
    summary: str | None = Field(
        default=None,
        description="One-line help text shown next to the command in parent --help output.",
    )
    description: str | None = Field(
        default=None,
        description="Long help text shown on `command --help`.",
    )
    positional: list[str] = Field(
        default_factory=list,
        description=(
            "Parameter names that should be exposed as positional args instead "
            "of flags. Order matters."
        ),
    )
    flag_aliases: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Override the flag names for specific parameters. "
            "e.g. ``{'destination_file_path': ['--path', '-p']}``. "
            "The list's first entry is the canonical flag; remaining entries "
            "are aliases."
        ),
    )
    formatters: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Named Jinja templates for response rendering. "
            "Users pick with ``--format <name>``. Unset → CLI falls back to "
            "built-in json/table formatters."
        ),
    )
    default_formatter: str = Field(
        default="json",
        description="Formatter name used when ``--format`` isn't passed.",
    )


def build_extension(spec: CLICommandSpec) -> dict[str, dict]:
    """Render a :class:`CLICommandSpec` into the OpenAPI-extra dict shape
    expected by FastAPI's ``openapi_extra=`` kwarg.
    """
    return {OPENAPI_EXTENSION_KEY: spec.model_dump(exclude_none=True, exclude_defaults=True)}
