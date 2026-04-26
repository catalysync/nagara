"""Named profiles for CLI-driven config switching.

A profile is a named bag of config overrides stored in
``~/.config/nagara/profiles.toml``. One profile is active at a time; the CLI
can switch between them without editing env vars or .env files.

File format::

    active = "dev"

    [profiles.dev]
    ENV = "development"
    LOG_LEVEL = "DEBUG"

    [profiles.prod]
    ENV = "production"
    SECRET_KEY = "..."   # no — keep secrets in env vars, not profiles on disk

Design notes
------------
- Profiles are ONLY for non-secret operational overrides (ENV, LOG_LEVEL, URLs,
  feature toggles). For secrets, use env vars or your secrets manager.
- The active profile is determined by, in order:
    1. ``NAGARA_PROFILE`` env var
    2. the ``active = "..."`` key in profiles.toml
    3. a caller-supplied default (usually ``"default"``)
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Profile:
    name: str
    overrides: dict[str, Any] = field(default_factory=dict)


class ProfileStore:
    """In-memory collection of profiles with a single active selection."""

    def __init__(self) -> None:
        self._profiles: dict[str, Profile] = {}
        self._active: str | None = None

    @property
    def active(self) -> str | None:
        return self._active

    def upsert(self, profile: Profile) -> None:
        self._profiles[profile.name] = profile

    def get(self, name: str) -> Profile:
        return self._profiles[name]

    def names(self) -> Iterable[str]:
        return list(self._profiles.keys())

    def activate(self, name: str) -> None:
        if name not in self._profiles:
            raise KeyError(name)
        self._active = name

    def remove(self, name: str) -> None:
        self._profiles.pop(name, None)
        if self._active == name:
            self._active = None


def save_profiles(store: ProfileStore, path: Path | str) -> None:
    """Write the store to disk as TOML. Creates parent dirs if needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if store.active is not None:
        # Manually emit a TOML string — avoids pulling in a third-party writer.
        lines.append(f'active = "{store.active}"')
        lines.append("")
    for name in store.names():
        profile = store.get(name)
        # Quote the section name so profiles like ``dev.local`` round-trip
        # correctly instead of becoming a nested ``profiles.dev.local`` table.
        escaped_name = name.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'[profiles."{escaped_name}"]')
        for key, value in profile.overrides.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    p.write_text("\n".join(lines))


def load_profiles(path: Path | str) -> ProfileStore:
    """Load a ProfileStore from disk. Returns an empty store if the file is missing."""
    p = Path(path)
    store = ProfileStore()
    if not p.is_file():
        return store
    with p.open("rb") as f:
        data = tomllib.load(f)
    for name, overrides in data.get("profiles", {}).items():
        if isinstance(overrides, dict):
            store.upsert(Profile(name=name, overrides=dict(overrides)))
    active = data.get("active")
    if isinstance(active, str) and active in store.names():
        # Go through activate() so the membership guard runs — keeps the
        # invariant that ``store._active`` always points at a real profile.
        store.activate(active)
    return store


def active_profile_name(*, store: ProfileStore | None = None, default: str = "default") -> str:
    """Return the active profile name. Resolution order:
    ``NAGARA_PROFILE`` env var → ``store.active`` (if a store is given) →
    ``default``. Matches the precedence used by ``TomlLayeredSource`` in
    ``config.py``."""
    env = os.environ.get("NAGARA_PROFILE")
    if env:
        return env
    if store is not None and store.active is not None:
        return store.active
    return default


def _toml_value(value: Any) -> str:
    """Minimal TOML value serializer — just the scalar types we support."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value).__name__}")
