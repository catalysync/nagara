"""Durable outbox for domain events.

The in-process :class:`nagara.events.EventBus` loses events if the process
crashes between ``session.commit()`` and ``bus.emit()``. Anywhere a handler
does work that must not be silently dropped on restart — external
integrations, durable side-effects, audit enrichment — that's unacceptable.
The outbox pattern fixes it:

1. Endpoint code calls :func:`emit_outboxed(session, event)` — INSERTs a row
   into ``outbox_events`` *inside the same transaction* as the state change.
   If the commit fails, the event disappears too. If the commit succeeds,
   the event is durable.
2. A separate process (cron job, k8s CronJob, background worker) periodically
   calls :func:`drain_once(session, bus)`. It reads unprocessed rows,
   reconstructs the typed event, dispatches to the in-process bus, and
   marks the row processed.

The drain step is idempotent and tolerates handler failures — the bus
already swallows handler exceptions, and the outbox records ``attempts`` +
``last_error`` so operators can see events that aren't making progress.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, fields
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Integer, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, UUIDPrimaryKeyMixin
from nagara.db.mixins import utcnow
from nagara.events import DomainEvent, EventBus, MemberAdded, OrgCreated, WorkspaceCreated

logger = logging.getLogger(__name__)


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    """One row per emitted event. Polled by the drain worker."""

    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


# Registry of event types the drain worker knows how to reconstruct. Adding a
# new event class means registering it here — otherwise drain will fail
# gracefully with ``last_error`` set to "unknown event_type".
_registry: dict[str, type[DomainEvent]] = {}


def register_event(event_type: type[DomainEvent]) -> type[DomainEvent]:
    """Register a DomainEvent subclass so the outbox drain can rebuild it."""
    _registry[event_type.__name__] = event_type
    return event_type


# Built-in events core emits.
for _evt in (OrgCreated, WorkspaceCreated, MemberAdded):
    register_event(_evt)


def _serialize(event: DomainEvent) -> dict[str, Any]:
    """Dataclass → JSON-safe dict. UUIDs and datetimes become strings."""
    out: dict[str, Any] = {}
    for k, v in asdict(event).items():
        if isinstance(v, UUID):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _deserialize(event_type: type[DomainEvent], payload: dict[str, Any]) -> DomainEvent:
    """JSON-safe dict → typed DomainEvent. Inverse of :func:`_serialize`."""
    kwargs: dict[str, Any] = {}
    for f in fields(event_type):
        raw = payload.get(f.name)
        if raw is None:
            kwargs[f.name] = None
            continue
        # Crude coercion based on the dataclass field annotation. Works for
        # the small set of types our events use (UUID, datetime, str, int).
        annotation = f.type if isinstance(f.type, type) else None
        if annotation is UUID or (isinstance(f.type, str) and "UUID" in f.type):
            kwargs[f.name] = UUID(raw) if isinstance(raw, str) else raw
        elif annotation is datetime or (isinstance(f.type, str) and "datetime" in f.type):
            kwargs[f.name] = datetime.fromisoformat(raw) if isinstance(raw, str) else raw
        else:
            kwargs[f.name] = raw
    return event_type(**kwargs)


def emit_outboxed(session: AsyncSession, event: DomainEvent) -> None:
    """Stage an event on the current session. The event becomes durable when
    the caller commits; rolls back with the transaction on error.

    Does *not* commit — the caller owns the transaction boundary so the
    event's fate tracks the state change exactly."""
    session.add(
        OutboxEvent(
            event_type=type(event).__name__,
            payload=_serialize(event),
            occurred_at=event.occurred_at,
        )
    )


async def drain_once(session: AsyncSession, bus: EventBus, batch_size: int = 100) -> int:
    """Process up to ``batch_size`` unprocessed events. Returns the number
    successfully dispatched.

    Intended to be called on a short interval by a separate worker. Safe to
    run concurrently across multiple workers — each takes a different batch
    thanks to the ``FOR UPDATE SKIP LOCKED`` semantics (added in a follow-up
    once we need HA workers; for now the simple batch is fine single-node).
    """
    stmt = (
        select(OutboxEvent)
        .where(OutboxEvent.processed_at.is_(None))
        .order_by(OutboxEvent.occurred_at)
        .limit(batch_size)
    )
    rows = list((await session.execute(stmt)).scalars().all())

    processed = 0
    for row in rows:
        event_cls = _registry.get(row.event_type)
        if event_cls is None:
            row.attempts += 1
            row.last_error = f"unknown event_type: {row.event_type}"
            logger.error("outbox drain: %s", row.last_error)
            continue

        try:
            evt = _deserialize(event_cls, row.payload)
            await bus.emit(evt)
        except Exception as exc:
            row.attempts += 1
            row.last_error = f"{type(exc).__name__}: {exc}"
            logger.exception("outbox drain failed for row %s", row.id)
            continue

        row.processed_at = datetime.now(UTC)
        processed += 1

    await session.commit()
    return processed
