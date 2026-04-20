"""Runtime secret scrubbing for log records.

A ``SecretScrubber`` is a :class:`logging.Filter` that holds a set of strings
and rewrites any log record whose message (or format args) contains one of
them, replacing each occurrence with ``***``.

Use case: even though :class:`pydantic.SecretStr` fields are masked in
``repr()``, a developer can still accidentally log a secret by calling
``.get_secret_value()`` and interpolating the result. This filter is the
last line of defense — attach it to the root logger so every handler
downstream is protected.

Typical wiring at app startup (e.g. FastAPI lifespan)::

    from nagara.secrets import install_secret_scrubber
    from nagara.config import settings

    install_secret_scrubber(settings=settings)
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nagara.config import Settings

_MASK = "***"


class SecretScrubber(logging.Filter):
    """Logging filter that redacts known secrets from log records."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: set[str] = set()

    def add(self, secret: str) -> None:
        """Register a secret string to redact. Empty/whitespace values are ignored."""
        if secret and secret.strip():
            self._secrets.add(secret)

    def extend(self, secrets: Iterable[str]) -> None:
        for s in secrets:
            self.add(s)

    def __contains__(self, secret: object) -> bool:
        return secret in self._secrets

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        # Format the message first (so %-style args are interpolated),
        # then redact the rendered string.
        try:
            message = record.getMessage()
        except TypeError, ValueError:
            return True
        redacted = message
        for secret in self._secrets:
            if secret in redacted:
                redacted = redacted.replace(secret, _MASK)
        if redacted != message:
            record.msg = redacted
            record.args = None
        return True

    def uninstall(self) -> None:
        """Detach this filter from the root logger."""
        root = logging.getLogger()
        if self in root.filters:
            root.removeFilter(self)


def install_secret_scrubber(
    *,
    settings: Settings | None = None,
    secrets: Iterable[str] = (),
) -> SecretScrubber:
    """Create a ``SecretScrubber``, populate it, and attach to the root logger.

    Scans ``settings`` for every ``SecretStr`` field and registers its real
    value. Additional literal secrets can be supplied via ``secrets=``.

    Returns the scrubber so callers can add more secrets at runtime.
    """
    from pydantic import SecretStr  # local import to avoid a circular dep on import order

    scrubber = SecretScrubber()
    if settings is not None:
        for name in type(settings).model_fields:
            value = getattr(settings, name, None)
            if isinstance(value, SecretStr):
                scrubber.add(value.get_secret_value())
    scrubber.extend(secrets)
    logging.getLogger().addFilter(scrubber)
    return scrubber
