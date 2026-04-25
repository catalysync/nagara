"""Pluggable secret backend.

Core reads runtime secrets through this interface rather than straight from
environment variables. The default backend *is* ``os.environ`` so OSS
self-hosters get the same behavior as before — no change unless you opt in.

Downstream apps or operators with a secret manager swap the default at
startup::

    from nagara.secret_backend import set_secret_backend
    from nagara.secret_backends.infisical import InfisicalSecretBackend

    set_secret_backend(InfisicalSecretBackend(
        token=settings.INFISICAL_TOKEN.get_secret_value(),
        project_id="...",
        environment="production",
    ))

The Infisical backend is an *optional* extra (`pip install nagara[infisical]`).
It's not imported from core — downstream apps opt in at their own startup.
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretBackend(Protocol):
    """Fetch a named secret. Returns ``None`` when the key isn't set, same
    shape as ``os.environ.get``."""

    async def get(self, name: str) -> str | None: ...


class EnvSecretBackend:
    """Default backend: reads from ``os.environ``. Zero dependencies."""

    async def get(self, name: str) -> str | None:
        return os.environ.get(name)


_backend: SecretBackend = EnvSecretBackend()


def get_secret_backend() -> SecretBackend:
    """Return the currently-registered backend."""
    return _backend


def set_secret_backend(backend: SecretBackend) -> None:
    """Replace the process-wide backend. Call at app startup, not per-request."""
    global _backend
    _backend = backend
