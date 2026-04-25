"""APIToken — PATs + service principals.

The hashed token (HMAC-SHA256 of the raw token) is stored — never the raw
token itself. The ``prefix`` is a short non-secret prefix shown in audit logs
and the UI so users can identify which token was used without unmasking it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, UUIDPrimaryKeyMixin
from nagara.db.mixins import utcnow


class APIToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "api_tokens"

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # HMAC-SHA256 hex digest is 64 chars; reserve more for future schemes.
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    # Short non-secret prefix shown in UI / audit logs (e.g., 'ng_pat_abcd').
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    scopes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
