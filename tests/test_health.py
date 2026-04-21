"""Health endpoint tests — /health/live, /health/ready, /health (alias)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from nagara.main import app

client = TestClient(app)


def test_health_alias_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_live_returns_ok():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_returns_503_when_db_unreachable():
    # Swap the whole probe engine with a stub whose connect() blows up.
    class Boom:
        def connect(self):
            raise RuntimeError("connection refused")

    with patch("nagara.main._probe_engine", Boom()):
        response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unready"
    assert "database" in body["reason"]


def test_health_ready_returns_ok_when_db_reachable():
    @asynccontextmanager
    async def _connect():
        conn = AsyncMock()
        conn.execute = AsyncMock(return_value=None)
        yield conn

    class Stub:
        def connect(self):
            return _connect()

    with patch("nagara.main._probe_engine", Stub()):
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
