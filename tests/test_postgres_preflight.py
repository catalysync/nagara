"""``_check_postgres_version`` startup hook fails fast on too-old servers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.engine import Result

from nagara.main import _check_postgres_version


def _stub_engine(version_num: int):
    """Return (engine_stub, executed) where ``executed`` is a list of the
    SQL strings the probe ran — lets tests assert the version SELECT
    actually fired instead of just not raising."""
    executed: list[str] = []

    @asynccontextmanager
    async def _connect():
        conn = AsyncMock()
        result = MagicMock(spec=Result)
        result.scalar_one.return_value = version_num

        async def _execute(stmt):
            executed.append(str(stmt))
            return result

        conn.execute = _execute
        yield conn

    class Stub:
        def connect(self):
            return _connect()

    return Stub(), executed


async def test_passes_when_server_version_meets_minimum():
    engine, executed = _stub_engine(160003)
    with patch("nagara.main._get_probe_engine", return_value=engine):
        await _check_postgres_version(None)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
    assert any("server_version_num" in s for s in executed), (
        "version probe SELECT must actually run"
    )


async def test_raises_when_server_version_below_minimum():
    engine, _ = _stub_engine(140002)
    with (
        patch("nagara.main._get_probe_engine", return_value=engine),
        pytest.raises(RuntimeError, match="major version 14"),
    ):
        await _check_postgres_version(None)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]


async def test_skipped_when_min_version_zero():
    from nagara.config import temporary_settings

    # Use temporary_settings rather than monkeypatching the module singleton —
    # consistent with the rest of the suite and respects the contextvar scope.
    with (
        temporary_settings(POSTGRES_MIN_VERSION=0),
        patch("nagara.main._get_probe_engine") as get_eng,
    ):
        await _check_postgres_version(None)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
    get_eng.assert_not_called()
