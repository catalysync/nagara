"""Domain events + in-process event bus.

Core emits typed events after successful writes. Any subscriber living in
the same process — a downstream app's startup hook, a plugin, an internal
worker — registers handlers at startup and reacts (audit enrichment,
external integrations, notifications, provisioning, metering, …).

The bus is deliberately simple: Python-only, no queue, no persistence. When
durable fan-out is needed, swap the :class:`EventBus` implementation behind
:func:`get_bus` — the call sites don't care.

Usage::

    from nagara.events import get_bus, WorkspaceCreated

    # emit site inside a domain endpoint
    await get_bus().emit(WorkspaceCreated(
        occurred_at=datetime.now(UTC),
        org_id=ws.org_id,
        workspace_id=ws.id,
        slug=ws.slug,
        created_by=ws.created_by,
    ))

    # downstream startup — subscribe
    get_bus().subscribe(WorkspaceCreated, my_handler)
    get_bus().subscribe(WorkspaceCreated, another_handler)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TypeVar
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainEvent:
    """Base for every event. Immutable so subscribers can't mutate each other's
    view of the event."""

    occurred_at: datetime


@dataclass(frozen=True)
class OrgCreated(DomainEvent):
    org_id: UUID
    slug: str


@dataclass(frozen=True)
class WorkspaceCreated(DomainEvent):
    org_id: UUID
    workspace_id: UUID
    slug: str
    created_by: UUID | None


@dataclass(frozen=True)
class MemberAdded(DomainEvent):
    workspace_id: UUID
    membership_id: UUID
    user_id: UUID | None
    group_id: UUID | None
    role: str


E = TypeVar("E", bound=DomainEvent)
Handler = Callable[[E], Awaitable[None]]


class EventBus:
    """In-process fan-out. Handlers run sequentially; a handler that raises is
    logged and the next handler still runs."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].append(handler)

    async def emit(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                await handler(event)
            except Exception:
                # One bad subscriber shouldn't starve the rest. Surface it in
                # logs and keep going.
                logger.exception("event handler %r failed for %s", handler, type(event).__name__)


_bus = EventBus()


def get_bus() -> EventBus:
    """Return the process-wide event bus. Replace the module global if you
    need a fresh bus in tests — :class:`EventBus` has no shared state beyond
    its handler dict."""
    return _bus
