"""The main engine must be disposed on app shutdown, not just the probe one."""

from __future__ import annotations

from nagara.db import session as _db_session  # noqa: F401 — ensures on_shutdown registers
from nagara.lifespan import _shutdown_hooks


def test_main_engine_dispose_registered_on_shutdown():
    # The session module registers its disposer at import time; confirm the
    # hook is in the shutdown registry under its known name.
    names = [getattr(hook, "__name__", "") for hook in _shutdown_hooks]
    assert "_dispose_engine" in names, (
        "nagara.db.session should register _dispose_engine via @on_shutdown so the "
        "main engine's pooled connections are returned cleanly on shutdown"
    )


def test_main_engine_is_the_one_being_disposed():
    # Defensive: make sure the hook references the module-level engine, not a
    # shadowing local.
    from nagara.db.session import _dispose_engine, engine  # noqa: F401

    # Check the closure cell binds the module-level engine by name.
    assert "engine" in _dispose_engine.__code__.co_names or any(
        cell.cell_contents is engine for cell in (_dispose_engine.__closure__ or ())
    )
