"""POST /orgs endpoint."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_create_org_returns_201_with_org(api_client: tuple[AsyncClient, Any]):
    client, _ = api_client
    res = await client.post("/orgs", json={"slug": "acme", "name": "Acme Inc"})
    assert res.status_code == 201
    body = res.json()
    assert body["slug"] == "acme"
    assert body["name"] == "Acme Inc"
    assert body["auth_provider"] == "local"
    assert "id" in body


@pytest.mark.asyncio
async def test_create_org_rejects_duplicate_slug(api_client: tuple[AsyncClient, Any]):
    client, _ = api_client
    first = await client.post("/orgs", json={"slug": "acme", "name": "Acme"})
    assert first.status_code == 201

    dup = await client.post("/orgs", json={"slug": "acme", "name": "Other"})
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_create_org_validates_required_fields(api_client: tuple[AsyncClient, Any]):
    client, _ = api_client
    res = await client.post("/orgs", json={"name": "missing slug"})
    assert res.status_code == 422


# Sanity: explicit OIDC / SAML protocols accepted (specific vendors configure
# through auth_config jsonb, not through the enum).
@pytest.mark.asyncio
async def test_create_org_with_oidc_protocol(api_client: tuple[AsyncClient, Any]):
    client, _ = api_client
    res = await client.post(
        "/orgs",
        json={
            "slug": "z",
            "name": "Z",
            "auth_provider": "oidc",
            "auth_config": {"issuer": "https://zitadel.example", "client_id": "abc"},
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["auth_provider"] == "oidc"
    assert body["auth_config"]["issuer"] == "https://zitadel.example"


@pytest_asyncio.fixture
async def api_client(session):
    from fastapi import FastAPI

    from nagara.db.session import get_session
    from nagara.org.api import router as org_router

    async def _override():
        yield session

    app = FastAPI()
    app.include_router(org_router)
    app.dependency_overrides[get_session] = _override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app
