"""FeatureResolver gating + WorkspaceCreated event emission on POST /workspaces.

These exercise the extension seams core exposes to the private cloud repo.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.events import EventBus, WorkspaceCreated
from nagara.features import FeatureCheck, FeatureResolver
from nagara.iam.model import User
from nagara.org.model import Org


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
async def test_workspace_created_event_fires_after_commit(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    import nagara.events as events

    received: list[WorkspaceCreated] = []

    async def handler(evt: WorkspaceCreated) -> None:
        received.append(evt)

    # Swap in a fresh bus so we don't leak handlers across tests.
    original = events._bus
    events._bus = EventBus()
    events._bus.subscribe(WorkspaceCreated, handler)
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
        assert res.status_code == 201
        assert len(received) == 1
        evt = received[0]
        assert evt.slug == "p"
        assert str(evt.org_id) == str(org.id)
        assert str(evt.workspace_id) == res.json()["id"]
        assert str(evt.created_by) == str(user.id)
    finally:
        events._bus = original


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
