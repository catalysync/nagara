"""Outbox — durable event emission that survives process crashes.

Events are written to ``outbox_events`` in the *same* transaction as the
state change. A drain worker picks them up, dispatches to the in-process
:class:`EventBus`, and marks them processed. The drain step is idempotent.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.events import EventBus, WorkspaceCreated
from nagara.outbox import OutboxEvent, drain_once, emit_outboxed


@pytest.mark.asyncio
async def test_emit_outboxed_persists_event_in_same_transaction(session: AsyncSession):
    evt = WorkspaceCreated(
        occurred_at=datetime.now(UTC),
        org_id=uuid4(),
        workspace_id=uuid4(),
        slug="p",
        created_by=None,
    )
    emit_outboxed(session, evt)
    await session.commit()

    rows = (await session.execute(select(OutboxEvent))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == "WorkspaceCreated"
    assert row.processed_at is None
    assert row.attempts == 0
    assert row.payload["slug"] == "p"


@pytest.mark.asyncio
async def test_emit_outboxed_rolled_back_if_transaction_fails(session: AsyncSession):
    evt = WorkspaceCreated(
        occurred_at=datetime.now(UTC),
        org_id=uuid4(),
        workspace_id=uuid4(),
        slug="p",
        created_by=None,
    )
    emit_outboxed(session, evt)
    await session.rollback()

    rows = (await session.execute(select(OutboxEvent))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_drain_dispatches_to_bus_and_marks_processed(session: AsyncSession):
    received: list[WorkspaceCreated] = []
    bus = EventBus()

    async def handler(e: WorkspaceCreated) -> None:
        received.append(e)

    bus.subscribe(WorkspaceCreated, handler)

    evt = WorkspaceCreated(
        occurred_at=datetime.now(UTC),
        org_id=uuid4(),
        workspace_id=uuid4(),
        slug="p",
        created_by=None,
    )
    emit_outboxed(session, evt)
    await session.commit()

    processed = await drain_once(session, bus)
    assert processed == 1
    assert len(received) == 1
    assert received[0].slug == "p"

    # Idempotent — running again processes nothing new.
    assert await drain_once(session, bus) == 0

    row = (await session.execute(select(OutboxEvent))).scalar_one()
    assert row.processed_at is not None


@pytest.mark.asyncio
async def test_drain_increments_attempts_on_handler_failure(session: AsyncSession):
    bus = EventBus()

    async def handler(_e: WorkspaceCreated) -> None:
        raise RuntimeError("boom")

    bus.subscribe(WorkspaceCreated, handler)

    emit_outboxed(
        session,
        WorkspaceCreated(
            occurred_at=datetime.now(UTC),
            org_id=uuid4(),
            workspace_id=uuid4(),
            slug="p",
            created_by=None,
        ),
    )
    await session.commit()

    # The bus swallows handler errors, so drain still marks the event
    # processed — the *bus* handles retry logic, not the outbox.
    processed = await drain_once(session, bus)
    assert processed == 1


@pytest.mark.asyncio
async def test_drain_skips_unknown_event_types(session: AsyncSession):
    # Manually insert a row with an event_type the registry doesn't know.
    session.add(
        OutboxEvent(
            event_type="DoesNotExist",
            payload={"foo": "bar"},
            occurred_at=datetime.now(UTC),
        )
    )
    await session.commit()

    # Drain should record an error and keep going — no crash.
    processed = await drain_once(session, EventBus())
    assert processed == 0

    row = (await session.execute(select(OutboxEvent))).scalar_one()
    assert row.processed_at is None
    assert row.attempts == 1
    assert row.last_error is not None
