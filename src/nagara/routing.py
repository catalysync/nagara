"""Custom ``APIRoute`` + ``APIRouter`` with project-wide cross-cutting
behavior. Import :class:`APIRouter` from here instead of FastAPI directly
so every route picks up:

  * Auto-commit of the SQLAlchemy session before the response is built
    (defense-in-depth alongside the dep-level commit in
    :func:`nagara.db.session.get_session`). Lets handlers safely return
    raw ORM objects without a manual commit dance.
  * OpenAPI inclusion driven by ``APITag.public`` / ``APITag.internal``
    so internal admin endpoints never leak into the published spec.

Tag a route ``tags=[APITag.internal, "admin"]`` to hide it from prod
OpenAPI; ``APITag.public`` to publish it; untagged routes default to
hidden so accidental endpoints don't ship.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from enum import StrEnum
from typing import Any

from fastapi import APIRouter as _FastAPIRouter
from fastapi.routing import APIRoute as _FastAPIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.config import settings


class APITag(StrEnum):
    """Routes tagged with these are filtered for OpenAPI inclusion."""

    public = "public"
    internal = "internal"


class AutoCommitAPIRoute(_FastAPIRoute):
    """Commit any ``AsyncSession`` argument right after the endpoint
    returns, before FastAPI serializes the response.

    Idempotent with the dep-level commit in :func:`get_session` — calling
    ``commit()`` twice is a no-op. The wrapper is here so handlers can
    return raw ORM objects whose attributes might lazy-load during
    serialization without the session having been closed first.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        # Only wrap async endpoints — sync endpoints can't hold an
        # AsyncSession (no await), so the wrapper has nothing to commit.
        if inspect.iscoroutinefunction(endpoint):
            endpoint = self._wrap(endpoint)
        super().__init__(path, endpoint, **kwargs)

    @staticmethod
    def _wrap(endpoint: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(endpoint)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            session: AsyncSession | None = None
            for v in (*args, *kwargs.values()):
                if isinstance(v, AsyncSession):
                    session = v
                    break
            try:
                response = await endpoint(*args, **kwargs)
            except BaseException:
                # Rollback before re-raising so the next caller of this
                # session doesn't inherit a tainted transaction.
                if session is not None:
                    await session.rollback()
                raise
            if session is not None:
                await session.commit()
            return response

        return wrapped


class IncludedInSchemaAPIRoute(_FastAPIRoute):
    """OpenAPI inclusion gated by :class:`APITag`.

    ``APITag.public`` → always in the spec.
    ``APITag.internal`` → only in dev's spec (so devs can browse internal
    endpoints in /docs locally; prod consumers never see them).
    Untagged → hidden by default.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)
        if not self.include_in_schema:
            return
        tags = self.tags or []
        if APITag.internal in tags:
            self.include_in_schema = settings.is_development()
        elif APITag.public in tags:
            self.include_in_schema = True
        else:
            self.include_in_schema = False


class APIRoute(AutoCommitAPIRoute, IncludedInSchemaAPIRoute):
    pass


class APIRouter(_FastAPIRouter):
    """Drop-in for ``fastapi.APIRouter`` that uses our custom ``APIRoute``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("route_class", APIRoute)
        super().__init__(*args, **kwargs)


__all__ = ["APIRoute", "APIRouter", "APITag"]
