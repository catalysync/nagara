"""``_check_postgres_version`` startup hook fails fast on too-old servers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.engine import Result

from nagara.main import _check_postgres_version


def _stub_engine(version_num: int):
    @asynccontextmanager
    async def _connect():
        conn = AsyncMock()
        # ``scalar_one`` is a sync method on Result — use MagicMock so the
        # whole stub surface stays consistent (no AsyncMock + sync-lambda mix).
        result = MagicMock(spec=Result)
        result.scalar_one.return_value = version_num
        conn.execute = AsyncMock(return_value=result)
        yield conn

    class Stub:
        def connect(self):
            return _connect()

    return Stub()


async def test_passes_when_server_version_meets_minimum():
    with patch("nagara.main._get_probe_engine", return_value=_stub_engine(160003)):
        await _check_postgres_version(None)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]


async def test_raises_when_server_version_below_minimum():
    with (
        patch("nagara.main._get_probe_engine", return_value=_stub_engine(140002)),
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
