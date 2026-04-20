"""Lazy environment-variable references.

An ``EnvVar`` is a string subclass that carries the NAME of an env var rather
than its value. The actual value is fetched only when ``.get_value()`` is
called (or via the recursive ``resolve()`` helper).

Typical use: user-supplied YAML config that references secrets indirectly::

    database:
      password: ${env:DB_PASSWORD}   # parsed into EnvVar("DB_PASSWORD")

The YAML parser converts the ``${env:X}`` form into an ``EnvVar`` instance,
which then sits in the config tree harmlessly until we need the real value.
This keeps secrets out of parsed config objects, logs, and repr dumps until
the last possible moment.
"""

from __future__ import annotations

import os
from typing import Any


class EnvVar(str):
    """A lazy reference to an environment variable.

    Subclasses ``str`` so it can stand in wherever a string is expected by
    type; at runtime, call ``.get_value()`` to resolve it.
    """

    __slots__ = ()

    def __new__(cls, name: str) -> EnvVar:
        return super().__new__(cls, name)

    @property
    def name(self) -> str:
        return str.__str__(self)

    def get_value(self, default: str | None = None) -> str:
        """Resolve to the current env-var value, or return ``default``.

        Raises :class:`KeyError` if the env var is unset AND no ``default`` is
        provided. (Missing-without-default is almost always a config bug, so
        failing loud is the right call.)
        """
        value = os.environ.get(self.name)
        if value is not None:
            return value
        if default is not None:
            return default
        raise KeyError(self.name)

    def __repr__(self) -> str:
        return f"EnvVar('env:{self.name}')"


def resolve(value: Any) -> Any:
    """Walk a nested structure, replacing every ``EnvVar`` with its resolved value.

    Handles dicts, lists, tuples, and sets recursively. Non-``EnvVar`` values
    pass through unchanged (even if they're strings that happen to contain
    ``${env:...}`` — that parsing happens upstream).
    """
    if isinstance(value, EnvVar):
        return value.get_value()
    if isinstance(value, dict):
        return {k: resolve(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v) for v in value]
    if isinstance(value, tuple):
        return tuple(resolve(v) for v in value)
    if isinstance(value, set):
        return {resolve(v) for v in value}
    return value
