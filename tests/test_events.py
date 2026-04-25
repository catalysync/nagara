"""Domain events + in-process EventBus."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from nagara.events import (
    DomainEvent,
    EventBus,
    MemberAdded,
    OrgCreated,
    WorkspaceCreated,
    get_bus,
)


def test_orgcreated_is_a_domain_event():
    assert issubclass(OrgCreated, DomainEvent)


def test_workspacecreated_is_a_domain_event():
    assert issubclass(WorkspaceCreated, DomainEvent)


def test_memberadded_is_a_domain_event():
    assert issubclass(MemberAdded, DomainEvent)


@pytest.mark.asyncio
async def test_bus_delivers_to_subscriber():
    bus = EventBus()
    received: list[OrgCreated] = []

    async def handler(evt: OrgCreated) -> None:
        received.append(evt)

    bus.subscribe(OrgCreated, handler)
    evt = OrgCreated(occurred_at=datetime.now(UTC), org_id=uuid4(), slug="acme")
    await bus.emit(evt)

    assert received == [evt]


@pytest.mark.asyncio
async def test_bus_delivers_to_multiple_subscribers_in_order():
    bus = EventBus()
    order: list[int] = []

    async def first(_evt: OrgCreated) -> None:
        order.append(1)

    async def second(_evt: OrgCreated) -> None:
        order.append(2)

    bus.subscribe(OrgCreated, first)
    bus.subscribe(OrgCreated, second)
    await bus.emit(OrgCreated(occurred_at=datetime.now(UTC), org_id=uuid4(), slug="x"))

    assert order == [1, 2]


@pytest.mark.asyncio
async def test_bus_does_not_deliver_unrelated_events():
    bus = EventBus()
    received: list[OrgCreated] = []

    async def handler(evt: OrgCreated) -> None:
        received.append(evt)

    bus.subscribe(OrgCreated, handler)
    await bus.emit(
        WorkspaceCreated(
            occurred_at=datetime.now(UTC),
            org_id=uuid4(),
            workspace_id=uuid4(),
            slug="p",
            created_by=None,
        )
    )

    assert received == []


@pytest.mark.asyncio
async def test_bus_handler_exceptions_dont_block_other_handlers():
    bus = EventBus()
    seen: list[str] = []

    async def breaks(_evt: OrgCreated) -> None:
        raise RuntimeError("boom")

    async def works(_evt: OrgCreated) -> None:
        seen.append("ok")

    bus.subscribe(OrgCreated, breaks)
    bus.subscribe(OrgCreated, works)
    await bus.emit(OrgCreated(occurred_at=datetime.now(UTC), org_id=uuid4(), slug="x"))

    assert seen == ["ok"]


def test_get_bus_returns_module_singleton():
    assert get_bus() is get_bus()
