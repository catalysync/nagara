"""JWT encode/decode — HS256 signed with ``settings.SECRET_KEY``.

HS256 is fine for a single-process app with a strong shared secret. When we
add horizontally-scaled token issuance across multiple services (or want to
hand out public verification keys), we'll migrate to RS256 — the
``encode_*`` / ``decode_token`` call shape stays the same so only this
module changes.

Tokens carry:

- ``sub`` — stringified user UUID
- ``kind`` — ``access`` vs ``refresh`` (prevents refresh-token replay into
  a protected endpoint)
- ``iat`` / ``exp`` — standard timestamps
- ``jti`` — opaque id; enables future revocation without a protocol change
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import jwt

from nagara.config import Settings

_ALGORITHM = "HS256"

ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)


class TokenKind(StrEnum):
    access = "access"
    refresh = "refresh"


def _encode(
    *,
    user_id: UUID,
    kind: TokenKind,
    ttl: timedelta,
    settings: Settings,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "kind": kind.value,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid4()),
    }
    secret = settings.SECRET_KEY.get_secret_value()
    if not secret:
        raise RuntimeError("NAGARA_SECRET_KEY is not set — cannot issue tokens")
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def encode_access_token(
    user_id: UUID,
    *,
    settings: Settings,
    ttl: timedelta = ACCESS_TTL,
) -> str:
    return _encode(user_id=user_id, kind=TokenKind.access, ttl=ttl, settings=settings)


def encode_refresh_token(
    user_id: UUID,
    *,
    settings: Settings,
    ttl: timedelta = REFRESH_TTL,
) -> str:
    return _encode(user_id=user_id, kind=TokenKind.refresh, ttl=ttl, settings=settings)


def decode_token(token: str, *, settings: Settings) -> dict[str, Any]:
    """Decode + verify signature and expiry. Raises on any failure."""
    secret = settings.SECRET_KEY.get_secret_value()
    return jwt.decode(token, secret, algorithms=[_ALGORITHM])
