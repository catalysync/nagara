"""FeatureResolver gating + outbox emission on POST /workspaces.

Exercises the extension seams core exposes to the private cloud repo.
Events are staged on the durable outbox in the same transaction as the
state change and drained by a separate worker — these tests walk that path
end-to-end to prove the integration.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.events import EventBus, WorkspaceCreated
from nagara.features import FeatureCheck, FeatureResolver
from nagara.iam.model import User
from nagara.org.model import Org
from nagara.outbox import OutboxEvent, drain_once


async def _seed(session: AsyncSession) -> tuple[Org, User]:
    org = Org(slug="acme", name="Acme")
    session.add(org)
    await session.commit()
    user = User(org_id=org.id, email="alice@example.com")
    session.add(user)
    await session.commit()
    return org, user


@pytest.mark.asyncio
async def test_feature_resolver_denial_returns_403(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    import nagara.features as features

    class Deny(FeatureResolver):
        async def can_create_workspace(self, org_id: UUID) -> FeatureCheck:
            return FeatureCheck(allowed=False, reason="plan quota exceeded")

    original = features.get_resolver()
    features.set_resolver(Deny())
    try:
        client, _ = api_client
        org, user = await _seed(session)
        res = await client.post(
            "/workspaces",
            json={
                "org_id": str(org.id),
                "slug": "p",
                "name": "P",
                "created_by": str(user.id),
            },
        )
        assert res.status_code == 403
        assert "plan quota exceeded" in res.json()["detail"]
    finally:
        features.set_resolver(original)


@pytest.mark.asyncio
async def test_workspace_created_event_landed_in_outbox(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    client, _ = api_client
    org, user = await _seed(session)
    res = await client.post(
        "/workspaces",
        json={
            "org_id": str(org.id),
            "slug": "p",
            "name": "P",
            "created_by": str(user.id),
        },
    )
    assert res.status_code == 201

    rows = (
        (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "WorkspaceCreated")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.processed_at is None
    assert row.payload["slug"] == "p"
    assert row.payload["org_id"] == str(org.id)
    assert row.payload["workspace_id"] == res.json()["id"]
    assert row.payload["created_by"] == str(user.id)


@pytest.mark.asyncio
async def test_draining_outbox_dispatches_to_subscribed_handler(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    client, _ = api_client
    org, user = await _seed(session)
    await client.post(
        "/workspaces",
        json={
            "org_id": str(org.id),
            "slug": "p",
            "name": "P",
            "created_by": str(user.id),
        },
    )

    bus = EventBus()
    received: list[WorkspaceCreated] = []

    async def handler(evt: WorkspaceCreated) -> None:
        received.append(evt)

    bus.subscribe(WorkspaceCreated, handler)
    processed = await drain_once(session, bus)

    assert processed == 1
    assert len(received) == 1
    assert received[0].slug == "p"
    assert received[0].org_id == org.id


@pytest_asyncio.fixture
async def api_client(session):
    from fastapi import FastAPI

    from nagara.db.session import get_session
    from nagara.workspace.api import router as ws_router

    async def _override():
        yield session

    app = FastAPI()
    app.include_router(ws_router)
    app.dependency_overrides[get_session] = _override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app
