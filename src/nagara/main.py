"""FastAPI entrypoint.

Exposes two separate health endpoints so Kubernetes can distinguish between
"is the process alive" (cheap) and "is it ready to serve" (DB reachable).

The app is built with a lifespan that walks the registries in
``nagara.lifespan``. Downstream apps import this module, register hooks
with ``@on_startup`` / ``@on_shutdown``, and serve ``app`` directly. The
``/health`` alias is retained so existing smoke tests and docker-compose
healthchecks keep working.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from nagara.config import settings
from nagara.exceptions import NagaraError, ValidationFailed
from nagara.lifespan import (
    _shutdown_hooks,
    _startup_hooks,
    build_lifespan,
    on_shutdown,
)
from nagara.logging import configure_logging
from nagara.middleware import RequestIDMiddleware, request_id_var
from nagara.rate_limit import limiter, rate_limit_exceeded_handler
from nagara.sentry import configure_sentry, mark_typed_error

configure_logging()
configure_sentry()

logger = logging.getLogger(__name__)


# Dedicated tiny engine for the readiness probe. Kept separate from the
# application's request-serving pool so a slow check can't exhaust it.
_probe_engine = create_async_engine(
    settings.get_postgres_dsn("asyncpg"),
    pool_size=1,
    max_overflow=0,
    pool_pre_ping=False,
)


@on_shutdown
async def _dispose_probe_engine(_app: FastAPI) -> None:
    """Dispose the probe engine on app shutdown so connections are returned
    cleanly rather than leaked to ``__del__``."""
    await _probe_engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=build_lifespan(_startup_hooks, _shutdown_hooks),
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_var.get() or "-"


@app.exception_handler(NagaraError)
async def nagara_error_handler(request: Request, exc: NagaraError) -> JSONResponse:
    rid = _request_id(request)
    mark_typed_error(exc)
    body: dict[str, object] = {
        "error": exc.error_code,
        "detail": exc.message,
        "request_id": rid,
    }
    if isinstance(exc, ValidationFailed) and exc.errors:
        body["errors"] = [e.model_dump() for e in exc.errors]
    if exc.extra:
        body["extra"] = exc.extra
    return JSONResponse(
        status_code=exc.status_code,
        content=body,
        headers={**exc.headers, "x-request-id": rid},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = _request_id(request)
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "detail": "internal server error",
            "request_id": rid,
        },
        headers={"x-request-id": rid},
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
