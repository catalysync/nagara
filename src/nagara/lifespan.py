"""FastAPI lifespan registry.

Core emits startup/shutdown callbacks through a global registry. Downstream
code that composes this package — an internal deployment, a third-party
wrapper, an integration layer — registers itself with ``@on_startup`` /
``@on_shutdown`` to plug in its :class:`FeatureResolver`, event subscribers,
external clients, background workers, and so on.

``nagara.main`` builds the app's lifespan context from the current contents
of these registries. Downstream consumers typically import ``nagara.main:app``
and register hooks before the app starts serving rather than building their
own app.

Example::

    # downstream/__init__.py — imported before the app starts
    from nagara.lifespan import on_startup, on_shutdown
    from nagara.events import get_bus, WorkspaceCreated
    from nagara.features import set_resolver

    @on_startup
    async def wire(_app):
        set_resolver(MyResolver())
        get_bus().subscribe(WorkspaceCreated, my_handler)

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
