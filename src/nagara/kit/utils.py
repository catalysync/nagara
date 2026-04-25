from __future__ import annotations

import uuid
from datetime import UTC, datetime


def utc_now() -> datetime:
    """tz-aware now() in UTC. Use as the python-side default for tz-aware
    DateTime columns and anywhere else you'd otherwise call ``datetime.utcnow()``
    (which returns a naive datetime — easy to misuse)."""
    return datetime.now(UTC)


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()
