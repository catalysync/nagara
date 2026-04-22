"""Built-in response formatters. More land in layer 1."""

from __future__ import annotations

import json
from typing import Any


def format_json(payload: Any) -> str:
    """Pretty-printed JSON. Always available via ``--json`` or
    ``--format json``, even when the endpoint declares server-side
    formatters."""
    return json.dumps(payload, indent=2, default=str)


BUILTIN_FORMATTERS = {"json": format_json}
