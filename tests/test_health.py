"""Health endpoint tests — /health/live, /health/ready, /health (alias)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import text

from nagara.main import app

client = TestClient(app)


def test_health_alias_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0


def test_health_live_returns_ok():
    response = client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "uptime_seconds" in body


def test_health_idle_disabled_by_default():
    response = client.get("/health/idle")
    assert response.status_code == 404
    assert response.json()["detail"] == "idle endpoint disabled"


def test_health_idle_when_enabled(monkeypatch):
    from nagara.config import settings

    monkeypatch.setattr(settings, "IDLE_TIMEOUT_SECONDS", 60)
    response = client.get("/health/idle")
    assert response.status_code == 200
    body = response.json()
    assert "idle_seconds" in body
    assert body["timeout_seconds"] == 60
    assert isinstance(body["should_shutdown"], bool)


def test_health_ready_returns_503_when_db_unreachable():
    class Boom:
        def connect(self):
            raise RuntimeError("connection refused")

    with patch("nagara.main._get_probe_engine", return_value=Boom()):
        response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unready"
    assert "database" in body["reason"]


def test_health_ready_returns_ok_when_db_reachable():
    """Verify the probe actually executes ``SELECT 1`` — a regression that
    swapped the statement to ``SELECT pg_sleep(60)`` would silently pass
    without this assertion."""
    executed: list[str] = []

    @asynccontextmanager
    async def _connect():
        conn = AsyncMock()

        async def _execute(stmt):
            executed.append(str(stmt))

        conn.execute = _execute
        yield conn

    class Stub:
        def connect(self):
            return _connect()

    with patch("nagara.main._get_probe_engine", return_value=Stub()):
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert executed == [str(text("SELECT 1"))]
