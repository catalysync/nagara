from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from nagara.config import settings
from nagara.middleware import request_id_var


def _client_key(request: Request) -> str:
    """Rate-limit key. Honors the leftmost ``X-Forwarded-For`` entry when
    the deploy declares it sits behind a trusted proxy — otherwise the
    limiter would key on the proxy IP and rate-limit the world as one."""
    if settings.TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            client = fwd.split(",", 1)[0].strip()
            if client:
                return client
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_key,
    storage_uri=settings.REDIS_URL,
    default_limits=[],
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    rid = getattr(request.state, "request_id", None) or request_id_var.get() or "-"
    retry_after = str(getattr(exc, "retry_after", 60))
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": str(exc.detail) if exc.detail else "rate limit exceeded",
            "request_id": rid,
        },
        headers={"Retry-After": retry_after, "x-request-id": rid},
    )
