from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.routing import APIRoute, APIRouter, APITag, AutoCommitAPIRoute


def _build_app() -> FastAPI:
    router = APIRouter()

    @router.get("/_public", tags=[APITag.public])
    def pub():
        return {"k": "public"}

    @router.get("/_internal", tags=[APITag.internal])
    async def intern():
        return {"k": "internal"}

    @router.get("/_untagged")
    def un():
        return {"k": "untagged"}

    app = FastAPI()
    app.include_router(router)
    return app


def test_routes_are_callable_at_runtime_regardless_of_tag():
    c = TestClient(_build_app())
    assert c.get("/_public").status_code == 200
    assert c.get("/_internal").status_code == 200
    assert c.get("/_untagged").status_code == 200


def test_openapi_includes_public_and_internal_in_dev():
    paths = sorted(_build_app().openapi()["paths"].keys())
    assert "/_public" in paths
    assert "/_internal" in paths
    assert "/_untagged" not in paths


def test_apirouter_uses_custom_route_class():
    router = APIRouter()
    assert router.route_class is APIRoute


def test_apitag_values_are_string():
    assert APITag.public.value == "public"
    assert APITag.internal.value == "internal"
    assert APITag.public != APITag.internal


def test_autocommit_skips_sync_endpoints():
    """Sync endpoints can't hold an AsyncSession; the wrapper should not
    try to await them or commit anything."""
    c = TestClient(_build_app())
    assert c.get("/_public").json() == {"k": "public"}


async def test_autocommit_wrapper_calls_commit_when_session_present():
    """Test the wrap function directly to avoid FastAPI route validation."""
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    async def handler(session):
        return {"ok": True}

    wrapped = AutoCommitAPIRoute._wrap(handler)
    result = await wrapped(session=mock_session)
    assert result == {"ok": True}
    mock_session.commit.assert_awaited_once()


async def test_autocommit_wrapper_skips_commit_when_no_session():
    async def handler():
        return {"k": "v"}

    wrapped = AutoCommitAPIRoute._wrap(handler)
    result = await wrapped()
    assert result == {"k": "v"}


async def test_autocommit_wrapper_finds_session_in_positional_args():
    mock_session = MagicMock(spec=AsyncSession)
    mock_session.commit = AsyncMock()

    async def handler(some_id, session):
        return {"id": some_id}

    wrapped = AutoCommitAPIRoute._wrap(handler)
    result = await wrapped("abc", mock_session)
    assert result == {"id": "abc"}
    mock_session.commit.assert_awaited_once()


def test_internal_routes_hidden_in_production_mode(monkeypatch):
    from nagara.config import settings
    monkeypatch.setattr(settings, "ENV", type(settings.ENV)("production"))
    paths = sorted(_build_app().openapi()["paths"].keys())
    assert "/_public" in paths
    assert "/_internal" not in paths
