"""OpenAPI-driven command line interface.

Commands are declared on API endpoints via :class:`CLIRouter` — the CLI
binary reads ``/openapi.json`` at startup and builds its argparse parser
from whatever it finds there. Adding an endpoint adds a command; no CLI
code changes.

See ``nagara-planning/09-cli-design.md`` for the full design.
"""

from nagara.cli.router import CLIRouter
from nagara.cli.schema import CLICommandSpec

__all__ = ["CLICommandSpec", "CLIRouter"]
