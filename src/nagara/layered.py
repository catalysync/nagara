"""Layered config loading + deep merge.

Composes multiple config sources (pyproject.toml, user TOML, env vars) into
one dict using a deep merge where later layers win. Lists are replaced, not
concatenated.

Typical usage at app startup::

    from nagara.layered import deep_merge, load_pyproject_config, load_toml_config

    config = deep_merge(
        load_pyproject_config(Path("pyproject.toml")),
        load_toml_config(Path.home() / ".nagara" / "config.toml"),
    )
"""

from __future__ import annotations

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any


def deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Merge ``b`` into ``a`` recursively and return a new dict.

    - Scalars in ``b`` replace those in ``a``.
    - Dicts are merged key-by-key, recursing into nested dicts.
    - Lists in ``b`` REPLACE lists in ``a`` (no concat).
    - Inputs are not mutated.
    """
    result = deepcopy(a)
    for key, value in b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_toml_config(path: Path | str) -> dict[str, Any]:
    """Read a plain TOML file and return its parsed content.

    Returns an empty dict if the file doesn't exist, so callers can layer
    optional files without always-on file-existence checks.
    """
    p = Path(path)
    if not p.is_file():
        return {}
    with p.open("rb") as f:
        return tomllib.load(f)


def load_pyproject_config(path: Path | str) -> dict[str, Any]:
    """Read ``pyproject.toml`` and return the ``[tool.nagara]`` table.

    Returns an empty dict if the file is missing or the table is absent.
    """
    data = load_toml_config(path)
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return {}
    nagara = tool.get("nagara", {})
    return nagara if isinstance(nagara, dict) else {}
