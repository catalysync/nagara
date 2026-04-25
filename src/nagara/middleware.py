from __future__ import annotations

import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
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
