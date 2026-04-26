"""FastAPI entrypoint.

Two health endpoints (live + ready) so Kubernetes can distinguish "process
up" from "ready to serve". The lifespan walks ``nagara.lifespan`` hooks
registered with ``@on_startup`` / ``@on_shutdown``.
"""

from __future__ import annotations

import functools
import logging
import time

_BOOT_TIME: float = time.monotonic()

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from nagara.config import settings
from nagara.exceptions import NagaraError, ValidationFailed
from nagara.lifespan import (
    _shutdown_hooks,
    _startup_hooks,
    build_lifespan,
    on_shutdown,
    on_startup,
)
from nagara.logging import configure_logging
from nagara.middleware import (
    ContentSizeLimitMiddleware,
    ForwardedPrefixMiddleware,
    LastRequestAtMiddleware,
    RequestCancelledMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    get_last_request_at,
    request_id_var,
)
from nagara.rate_limit import limiter, rate_limit_exceeded_handler
from nagara.sentry import configure_sentry, mark_typed_error

configure_logging()
configure_sentry()

logger = logging.getLogger(__name__)


@functools.cache
def _get_probe_engine() -> AsyncEngine:
    """Tiny, lazily-built engine for the readiness probe. Kept separate
    from the application's request-serving pool so a slow check can't
    exhaust it. Cached so subsequent calls share one engine; tests can
    swap by patching ``nagara.main._get_probe_engine``."""
    return create_async_engine(
        settings.get_postgres_dsn("asyncpg"),
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=False,
    )


@on_shutdown
async def _dispose_probe_engine(_app: FastAPI) -> None:
    if "_get_probe_engine" in globals() and _get_probe_engine.cache_info().currsize:
        await _get_probe_engine().dispose()
        _get_probe_engine.cache_clear()


@on_startup
async def _check_postgres_version(_app: FastAPI) -> None:
    """Fail-fast if the connected Postgres is older than the configured
    minimum. Cheap one-shot SELECT during startup; saves baffling
    runtime errors when a deploy lands on an unsupported server."""
    if settings.POSTGRES_MIN_VERSION == 0:
        return
    engine = _get_probe_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW server_version_num"))
        version_num = int(result.scalar_one())
    major = version_num // 10000
    if major < settings.POSTGRES_MIN_VERSION:
        raise RuntimeError(
            f"PostgreSQL {major} is older than the configured minimum "
            f"{settings.POSTGRES_MIN_VERSION}. Upgrade the server or set "
            f"NAGARA_POSTGRES_MIN_VERSION to override."
        )


@on_startup
async def _check_production_secrets(_app: FastAPI) -> None:
    """Refuse to boot in production with default-or-empty secrets."""
    if not settings.is_production():
        return
    if not settings.SECRET_KEY.get_secret_value():
        raise RuntimeError(
            "NAGARA_SECRET_KEY is empty. Generate one with "
            "`python -c 'import secrets; print(secrets.token_urlsafe(64))'`."
        )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or request_id_var.get() or "-"


def create_app() -> FastAPI:
    """Build a fresh ``FastAPI`` instance. Tests use this to get an isolated
    app per session without import-side-effect surprises; production calls
    it once at module load."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=build_lifespan(_startup_hooks, _shutdown_hooks),
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    if settings.TRUST_PROXY:
        app.add_middleware(ForwardedPrefixMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(LastRequestAtMiddleware)
    app.add_middleware(RequestCancelledMiddleware)
    app.add_middleware(ContentSizeLimitMiddleware, max_bytes=settings.REQUEST_MAX_BYTES)
    app.add_middleware(RequestIDMiddleware)
    if settings.CORS_ALLOW_CREDENTIALS and "*" in settings.CORS_ORIGINS:
        raise RuntimeError(
            "CORS_ALLOW_CREDENTIALS=True is incompatible with a wildcard "
            "in CORS_ORIGINS. Browsers strip the wildcard silently and the "
            "app appears broken. List explicit origins, or turn credentials off."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    def health_live() -> dict[str, object]:
        return {
            "status": "ok",
            "version": settings.RELEASE_VERSION,
            "uptime_seconds": int(time.monotonic() - _BOOT_TIME),
        }

    @app.get("/health/ready", tags=["health"])
    async def health_ready() -> JSONResponse:
        try:
            async with _get_probe_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            logger.warning("readiness probe failed: %s", exc)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unready", "reason": "database unreachable"},
            )
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.get("/health", tags=["health"])
    def health() -> dict[str, object]:
        return health_live()

    @app.get("/health/idle", tags=["health"])
    def health_idle() -> JSONResponse:
        if settings.IDLE_TIMEOUT_SECONDS == 0:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "idle endpoint disabled"},
            )
        idle = int(time.monotonic() - get_last_request_at())
        return JSONResponse(
            status_code=200,
            content={
                "idle_seconds": idle,
                "timeout_seconds": settings.IDLE_TIMEOUT_SECONDS,
                "should_shutdown": idle >= settings.IDLE_TIMEOUT_SECONDS,
            },
        )

    return app


app = create_app()
