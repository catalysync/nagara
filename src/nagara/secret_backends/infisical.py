"""Infisical-backed :class:`SecretBackend`.

Install with ``pip install nagara[infisical]`` (or ``uv sync --extra
infisical``). The SDK is imported lazily inside the class so importing this
module without the extra doesn't crash — it raises only when constructed.

Usage::

    from nagara.secret_backends.infisical import InfisicalSecretBackend
    from nagara.secret_backend import set_secret_backend

    set_secret_backend(InfisicalSecretBackend(
        token=os.environ["INFISICAL_TOKEN"],
        project_id="prj_abc",
        environment="production",
    ))

Reads are cached in-process keyed by (path, name); call
``InfisicalSecretBackend.invalidate()`` after rotation events.
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class InfisicalSecretBackend:
    """Proxy that fetches from Infisical on first read and caches thereafter.

    The Infisical Python SDK's public surface is synchronous; we wrap calls
    in ``asyncio.to_thread`` so this class still satisfies the async
    ``SecretBackend`` protocol without blocking the event loop.
    """

    def __init__(
        self,
        *,
        token: str,
        project_id: str,
        environment: str = "production",
        secret_path: str = "/",
        site_url: str = "https://app.infisical.com",
    ) -> None:
        try:
            # SDK package: ``infisicalsdk`` (v1+). Installed via the
            # ``infisical`` extras.
            from infisicalsdk import InfisicalSDKClient  # ty: ignore[unresolved-import]
        except ImportError as exc:  # pragma: no cover — exercised in integration
            raise RuntimeError(
                "infisical extra is not installed — pip install nagara[infisical]"
            ) from exc

        self._client = InfisicalSDKClient(host=site_url, token=token)
        self._project_id = project_id
        self._environment = environment
        self._path = secret_path
        self._cache: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get(self, name: str) -> str | None:
        # Cheap path — no lock when cache has the value.
        if name in self._cache:
            return self._cache[name]

        async with self._lock:
            # Another waiter may have populated the entry.
            if name in self._cache:
                return self._cache[name]
            try:
                secret = await asyncio.to_thread(
                    self._client.secrets.get_secret_by_name,
                    secret_name=name,
                    project_id=self._project_id,
                    environment_slug=self._environment,
                    secret_path=self._path,
                )
            except Exception as exc:
                logger.warning("infisical fetch failed for %s: %s", name, exc)
                return None

            value = getattr(secret, "secret_value", None) or getattr(secret, "value", None)
            if value is None:
                return None
            self._cache[name] = value
            return value

    def invalidate(self) -> None:
        """Clear the in-process cache. Call after a known rotation event."""
        self._cache.clear()
