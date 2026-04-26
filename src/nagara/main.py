"""FastAPI entrypoint.

Two health endpoints (live + ready) so Kubernetes can distinguish "process
up" from "ready to serve". The lifespan walks ``nagara.lifespan`` hooks
registered with ``@on_startup`` / ``@on_shutdown``.
"""

from __future__ import annotations

import functools
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from nagara.config import get_current_settings, settings, verify_settings
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
    RequestCancelledMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
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
    swap by patching ``nagara.main._get_probe_engine``.

    The cache is keyed on no arguments and the DSN is read from the
    module-level ``settings`` singleton at first call. ``temporary_settings``
    DSN swaps after first use will *not* be picked up by the cached engine —
    intentional, since startup is the only legitimate caller and settings
    are immutable in production.
    """
    return create_async_engine(
        settings.get_postgres_dsn("asyncpg"),
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=False,
    )


@on_shutdown
async def _dispose_probe_engine(_app: FastAPI) -> None:
    if _get_probe_engine.cache_info().currsize:
        await _get_probe_engine().dispose()
        _get_probe_engine.cache_clear()


@on_startup
async def _check_postgres_version(_app: FastAPI) -> None:
    """Fail-fast if the connected Postgres is older than the configured
    minimum. Cheap one-shot SELECT during startup; saves baffling
    runtime errors when a deploy lands on an unsupported server."""
    s = get_current_settings()
    if s.POSTGRES_MIN_VERSION == 0:
        return
    engine = _get_probe_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SHOW server_version_num"))
        version_num = int(result.scalar_one())
    major = version_num // 10000
    if major < s.POSTGRES_MIN_VERSION:
        raise RuntimeError(
            f"server reports PostgreSQL major version {major}; "
            f"NAGARA_POSTGRES_MIN_VERSION is {s.POSTGRES_MIN_VERSION}. "
            f"Upgrade the server or lower the configured minimum."
        )


@on_startup
async def _verify_production_settings(_app: FastAPI) -> None:
    verify_settings(settings)


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
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # ty:ignore[invalid-argument-type]

    if settings.TRUST_PROXY:
        app.add_middleware(ForwardedPrefixMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RequestCancelledMiddleware,
        poll_seconds=settings.REQUEST_CANCEL_POLL_SECONDS,
    )
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
        # Surface the exception class name (never the message) so first-line
        # ops can categorize incidents without grepping logs. The class name
        # is safe — it never contains user input.
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "detail": f"internal server error: {type(exc).__name__}",
                "request_id": rid,
            },
            headers={"x-request-id": rid},
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {"hello": "world"}

    @app.get("/health/live", tags=["health"])
    def health_live() -> dict[str, str]:
        return {"status": "ok", "version": settings.RELEASE_VERSION}

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
    def health() -> dict[str, str]:
        return health_live()

    return app


app = create_app()
