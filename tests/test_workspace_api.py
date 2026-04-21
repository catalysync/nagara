"""POST /workspaces (with auto-default env), GET /workspaces, POST members."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.iam.model import Group, User
from nagara.org.model import Org
from nagara.workspace.model import Environment


async def _seed(session: AsyncSession) -> tuple[Org, User]:
    org = Org(slug="acme", name="Acme")
    session.add(org)
    await session.commit()
    user = User(org_id=org.id, email="alice@example.com")
    session.add(user)
    await session.commit()
    return org, user


@pytest.mark.asyncio
async def test_create_workspace_creates_default_environment(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    client, _ = api_client
    org, user = await _seed(session)
    res = await client.post(
        "/workspaces",
        json={
            "org_id": str(org.id),
            "slug": "proj",
            "name": "Proj",
            "created_by": str(user.id),
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["slug"] == "proj"
    ws_id = body["id"]

    envs = (
        (await session.execute(select(Environment).where(Environment.workspace_id == UUID(ws_id))))
        .scalars()
        .all()
    )
    assert len(envs) == 1
    assert envs[0].slug == "default"
    assert envs[0].is_default is True


@pytest.mark.asyncio
async def test_list_workspaces_filtered_by_org(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    client, _ = api_client
    org_a, user_a = await _seed(session)

    org_b = Org(slug="other", name="Other")
    session.add(org_b)
    await session.commit()

    await client.post(
        "/workspaces",
        json={"org_id": str(org_a.id), "slug": "p1", "name": "P1", "created_by": str(user_a.id)},
    )
    await client.post(
        "/workspaces",
        json={"org_id": str(org_a.id), "slug": "p2", "name": "P2", "created_by": str(user_a.id)},
    )
    await client.post(
        "/workspaces",
        json={"org_id": str(org_b.id), "slug": "p3", "name": "P3"},
    )

    res = await client.get(f"/workspaces?org_id={org_a.id}")
    assert res.status_code == 200
    slugs = sorted(w["slug"] for w in res.json())
    assert slugs == ["p1", "p2"]


@pytest.mark.asyncio
async def test_create_workspace_rejects_duplicate_slug_in_org(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    client, _ = api_client
    org, user = await _seed(session)
    first = await client.post(
        "/workspaces",
        json={"org_id": str(org.id), "slug": "p", "name": "P", "created_by": str(user.id)},
    )
    assert first.status_code == 201

    dup = await client.post(
        "/workspaces",
        json={"org_id": str(org.id), "slug": "p", "name": "Other", "created_by": str(user.id)},
    )
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_add_user_member(api_client: tuple[AsyncClient, Any], session: AsyncSession):
    client, _ = api_client
    org, user = await _seed(session)
    ws_res = await client.post(
        "/workspaces",
        json={"org_id": str(org.id), "slug": "p", "name": "P", "created_by": str(user.id)},
    )
    ws_id = ws_res.json()["id"]

    res = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_id": str(user.id), "role": "editor"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["user_id"] == str(user.id)
    assert body["group_id"] is None
    assert body["role"] == "editor"


@pytest.mark.asyncio
async def test_add_group_member(api_client: tuple[AsyncClient, Any], session: AsyncSession):
    client, _ = api_client
    org, user = await _seed(session)
    group = Group(org_id=org.id, name="engineers")
    session.add(group)
    await session.commit()

    ws_res = await client.post(
        "/workspaces",
        json={"org_id": str(org.id), "slug": "p", "name": "P", "created_by": str(user.id)},
    )
    ws_id = ws_res.json()["id"]

    res = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"group_id": str(group.id), "role": "viewer"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["group_id"] == str(group.id)
    assert body["user_id"] is None


@pytest.mark.asyncio
async def test_add_member_requires_user_xor_group(
    api_client: tuple[AsyncClient, Any], session: AsyncSession
):
    client, _ = api_client
    org, user = await _seed(session)
    ws_res = await client.post(
        "/workspaces",
        json={"org_id": str(org.id), "slug": "p", "name": "P", "created_by": str(user.id)},
    )
    ws_id = ws_res.json()["id"]

    # Neither set.
    res = await client.post(f"/workspaces/{ws_id}/members", json={"role": "editor"})
    assert res.status_code == 422

    # Both set.
    res = await client.post(
        f"/workspaces/{ws_id}/members",
        json={"user_id": str(user.id), "group_id": str(user.id), "role": "editor"},
    )
    assert res.status_code == 422


@pytest_asyncio.fixture
async def api_client(session):
    from fastapi import FastAPI

    from nagara.db.session import get_session
    from nagara.org.api import router as org_router
    from nagara.workspace.api import router as ws_router

    async def _override():
        yield session

    app = FastAPI()
    app.include_router(org_router)
    app.include_router(ws_router)
    app.dependency_overrides[get_session] = _override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app
