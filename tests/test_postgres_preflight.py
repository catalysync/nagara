"""``_check_postgres_version`` startup hook fails fast on too-old servers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from nagara.main import _check_postgres_version


def _stub_engine(version_num: int):
    @asynccontextmanager
    async def _connect():
        conn = AsyncMock()
        result = AsyncMock()
        result.scalar_one = lambda: version_num
        conn.execute = AsyncMock(return_value=result)
        yield conn

    class Stub:
        def connect(self):
            return _connect()

    return Stub()


async def test_passes_when_server_version_meets_minimum():
    with patch("nagara.main._get_probe_engine", return_value=_stub_engine(160003)):
        await _check_postgres_version(None)  # type: ignore[arg-type]


async def test_raises_when_server_version_below_minimum():
    with patch("nagara.main._get_probe_engine", return_value=_stub_engine(140002)):
        with pytest.raises(RuntimeError, match="PostgreSQL 14 is older than"):
            await _check_postgres_version(None)  # type: ignore[arg-type]


async def test_skipped_when_min_version_zero(monkeypatch):
    from nagara.config import settings

    monkeypatch.setattr(settings, "POSTGRES_MIN_VERSION", 0)
    # Should return without consulting the engine — patch is_called to confirm.
    with patch("nagara.main._get_probe_engine") as get_eng:
        await _check_postgres_version(None)  # type: ignore[arg-type]
    get_eng.assert_not_called()
