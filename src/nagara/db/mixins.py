"""Reusable column mixins for SQLAlchemy models.

Compose by multiple-inheriting alongside ``Base``::

    class Org(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
        __tablename__ = "orgs"
        ...
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UUIDPrimaryKeyMixin:
    """Adds an ``id`` column populated client-side with UUID4. Uses SQLAlchemy
    ``Uuid`` which renders as ``uuid`` on Postgres and ``CHAR(32)`` elsewhere."""

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)


class TimestampedMixin:
    """Adds ``created_at`` / ``updated_at`` (both NOT NULL, server-stamped)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        server_default=func.now(),
    )


class SoftDeleteMixin:
    """Adds a nullable ``deleted_at``. Filter on ``deleted_at IS NULL`` to scope
    queries to the live set."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
