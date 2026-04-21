"""FastAPI entrypoint.

Exposes two separate health endpoints so Kubernetes can distinguish between
"is the process alive" (cheap) and "is it ready to serve" (DB reachable).

The ``/health`` alias is retained so existing smoke tests and docker-compose
healthchecks keep working.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from nagara.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

# Dedicated tiny engine for the readiness probe. Kept separate from the
# application's request-serving pool so a slow check can't exhaust it.
_probe_engine = create_async_engine(
    settings.get_postgres_dsn("asyncpg"),
    pool_size=1,
    max_overflow=0,
    pool_pre_ping=False,
)


@app.get("/")
def root() -> dict[str, str]:
    return {"hello": "world"}


@app.get("/health/live", tags=["health"])
def health_live() -> dict[str, str]:
    """Liveness — the process is up. No dependency checks; must stay cheap so
    k8s can call it frequently without load.
    """
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def health_ready() -> JSONResponse:
    """Readiness — ``SELECT 1`` against Postgres. 503 when the DB is
    unreachable so k8s pulls the pod out of the Service endpoint list during
    outages without killing it outright.
    """
    try:
        async with _probe_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("readiness probe failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unready", "reason": "database unreachable"},
        )
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Back-compat alias for ``/health/live``. Kept so existing docker-compose
    healthchecks don't break.
    """
    return {"status": "ok"}
