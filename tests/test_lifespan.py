"""Lifespan hooks — core exposes a registry cloud can plug startup/shutdown into."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nagara.lifespan import build_lifespan, on_shutdown, on_startup


def test_startup_hooks_run_in_registration_order():
    order: list[str] = []

    async def first(_app: FastAPI) -> None:
        order.append("first")

    async def second(_app: FastAPI) -> None:
        order.append("second")

    app = FastAPI(lifespan=build_lifespan([first, second], []))
    with TestClient(app):
        pass
    assert order == ["first", "second"]


def test_shutdown_hooks_run_in_reverse_registration_order():
    order: list[str] = []

    async def first(_app: FastAPI) -> None:
        order.append("first")

    async def second(_app: FastAPI) -> None:
        order.append("second")

    app = FastAPI(lifespan=build_lifespan([], [first, second]))
    with TestClient(app):
        pass
    # Reversed so teardown undoes setup in LIFO order.
    assert order == ["second", "first"]


def test_on_startup_decorator_registers_globally():
    import nagara.lifespan as mod

    # Snapshot and clear the global registries so this test is hermetic.
    saved_up = mod._startup_hooks[:]
    saved_down = mod._shutdown_hooks[:]
    mod._startup_hooks.clear()
    mod._shutdown_hooks.clear()
    try:
        called: list[str] = []

        @on_startup
        async def hook(_app: FastAPI) -> None:
            called.append("up")

        @on_shutdown
        async def shut(_app: FastAPI) -> None:
            called.append("down")

        app = FastAPI(lifespan=build_lifespan(mod._startup_hooks, mod._shutdown_hooks))
        with TestClient(app):
            pass
        assert called == ["up", "down"]
    finally:
        mod._startup_hooks[:] = saved_up
        mod._shutdown_hooks[:] = saved_down


def test_startup_exception_prevents_app_from_starting():
    import pytest

    async def fails(_app: FastAPI) -> None:
        raise RuntimeError("boom")

    app = FastAPI(lifespan=build_lifespan([fails], []))
    with pytest.raises(RuntimeError, match="boom"), TestClient(app):
        pass
