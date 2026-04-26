"""FastAPI lifespan registry.

Modules register startup/shutdown callbacks with ``@on_startup`` /
``@on_shutdown``; ``nagara.main`` reads those registries when building the
app's lifespan context.

Example::

    from nagara.lifespan import on_shutdown

    @on_shutdown
    async def drain(_app):
        await my_client.aclose()
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI

LifespanHook = Callable[[FastAPI], Awaitable[None]]


# Module-global lists so decorators can register at import time. Downstream
# consumers import core first, then register their hooks; core's main module
# reads these when it builds the app's lifespan.
_startup_hooks: list[LifespanHook] = []
_shutdown_hooks: list[LifespanHook] = []


def on_startup(fn: LifespanHook) -> LifespanHook:
    """Register ``fn`` to run once when the app starts. Runs in registration
    order, before any request is served."""
    _startup_hooks.append(fn)
    return fn


def on_shutdown(fn: LifespanHook) -> LifespanHook:
    """Register ``fn`` to run once when the app exits. Runs in *reverse*
    registration order so teardown undoes setup in LIFO order."""
    _shutdown_hooks.append(fn)
    return fn


def build_lifespan(
    startup: Iterable[LifespanHook],
    shutdown: Iterable[LifespanHook],
):
    """Build a FastAPI-compatible lifespan context manager from hook lists.

    Takes the lists as arguments (rather than reading globals) so tests can
    exercise isolated hook sets without leaking into the process-wide
    registry.
    """
    startup = list(startup)
    shutdown = list(shutdown)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        for hook in startup:
            await hook(app)
        try:
            yield
        finally:
            for hook in reversed(shutdown):
                await hook(app)

    return lifespan
