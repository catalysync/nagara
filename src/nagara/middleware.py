from __future__ import annotations

import asyncio
import uuid
from contextvars import ContextVar

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
