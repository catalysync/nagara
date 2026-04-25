from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Iterable
from contextvars import ContextVar
from urllib.parse import urlencode

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp


request_id_var: ContextVar[str] = ContextVar("request_id", default="")


# 128 chars covers UUIDs, 64-char hex tokens, and prefixed forms. Anything
# longer or with control chars is almost certainly an attempt at log/header
# injection — fall back to a fresh UUID rather than echo back unbounded.
_RID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")



class RequestIDMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, header_name: str = "x-request-id") -> None:
        super().__init__(app)
        self._header = header_name

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        inbound = request.headers.get(self._header)
        rid = inbound if inbound and _RID_RE.match(inbound) else uuid.uuid4().hex
        request.state.request_id = rid
        token = request_id_var.set(rid)
        # bind into structlog's context so merge_contextvars picks it up on
        # every log record emitted during this request — covers both our
        # structlog calls and stdlib logger calls routed through dictConfig.
        structlog.contextvars.bind_contextvars(request_id=rid)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[self._header] = rid
        return response


class RequestCancelledMiddleware(BaseHTTPMiddleware):
    """If the client disconnects mid-request, cancel the handler and
    return 499. Without this, dropped browser tabs leave handlers running
    until their natural completion — wasted CPU + held DB sessions."""

    def __init__(self, app: ASGIApp, *, poll_seconds: float = 0.1) -> None:
        super().__init__(app)
        self._poll = poll_seconds

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        async def watch_disconnect() -> None:
            while True:
                if await request.is_disconnected():
                    return
                await asyncio.sleep(self._poll)

        handler = asyncio.create_task(call_next(request))
        watcher = asyncio.create_task(watch_disconnect())

        done, pending = await asyncio.wait(
            [handler, watcher], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()

        if watcher in done:
            return Response("client disconnected", status_code=499)
        return await handler


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose body exceeds ``max_bytes`` with 413 before any
    handler runs. Trusts ``Content-Length`` when present; otherwise streams
    the body and aborts as soon as the running total crosses the cap."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        super().__init__(app)
        self._max = max_bytes

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > self._max:
                    return self._too_large()
            except ValueError:
                pass
        return await call_next(request)

    def _too_large(self) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content={
                "error": "payload_too_large",
                "detail": f"request body exceeds {self._max} bytes",
            },
        )


_BOUNDARY_RE = re.compile(r"^[\w\-]{1,70}$")


def _parse_content_type(value: str) -> tuple[str, dict[str, str]]:
    """Parse a Content-Type header into (media_type, params).
    Handles ``multipart/form-data; boundary=abc; charset=UTF-8`` and
    quoted-string boundaries per RFC 7231 / 9112."""
    if not value:
        return "", {}
    parts = [p.strip() for p in value.split(";")]
    media_type = parts[0].lower()
    params: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        params[k.strip().lower()] = v.strip().strip('"')
    return media_type, params


class MultipartBoundaryMiddleware(BaseHTTPMiddleware):
    """Validate ``Content-Type: multipart/form-data; boundary=...`` syntax
    on configured paths before FastAPI's parser sees the body. Rejects
    malformed boundaries with 422 — defends against a known
    python-multipart hang-on-bad-boundary class of bug."""

    def __init__(self, app: ASGIApp, *, paths: Iterable[str]) -> None:
        super().__init__(app)
        self._paths = tuple(paths)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not any(request.url.path.startswith(p) for p in self._paths):
            return await call_next(request)
        ct = request.headers.get("content-type", "")
        media_type, params = _parse_content_type(ct)
        if media_type != "multipart/form-data" or "boundary" not in params:
            return self._reject("Content-Type must be multipart/form-data with a boundary")
        if not _BOUNDARY_RE.match(params["boundary"]):
            return self._reject("invalid multipart boundary")
        return await call_next(request)

    def _reject(self, detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_multipart", "detail": detail},
        )


class ForwardedPrefixMiddleware(BaseHTTPMiddleware):
    """Honour ``X-Forwarded-Prefix`` set by a reverse proxy. The prefix
    is propagated into ASGI ``scope["root_path"]`` so URL builders
    downstream emit absolute paths that include it (matters for SSE
    callbacks, OAuth redirects, anything that handed-out URLs)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        prefix = request.headers.get("x-forwarded-prefix")
        if prefix:
            request.scope["root_path"] = prefix.rstrip("/")
        return await call_next(request)


class QueryListFlattenMiddleware(BaseHTTPMiddleware):
    """Rewrite ``?ids=a,b,c`` → ``?ids=a&ids=b&ids=c`` for an explicit
    set of keys so FastAPI's ``list[str]`` parsing accepts both styles.
    Opt-in per key — never global — so a value with a literal comma
    isn't unexpectedly split."""

    def __init__(self, app: ASGIApp, *, keys: Iterable[str]) -> None:
        super().__init__(app)
        self._keys = frozenset(keys)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        flattened: list[tuple[str, str]] = []
        changed = False
        for key, value in request.query_params.multi_items():
            if key in self._keys and "," in value:
                flattened.extend((key, v) for v in value.split(",") if v)
                changed = True
            else:
                flattened.append((key, value))
        if changed:
            request.scope["query_string"] = urlencode(flattened, doseq=True).encode()
        return await call_next(request)
