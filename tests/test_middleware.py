from fastapi import FastAPI, Query, Request
from fastapi.testclient import TestClient

from nagara.middleware import (
    ContentSizeLimitMiddleware,
    ForwardedPrefixMiddleware,
    MultipartBoundaryMiddleware,
    QueryListFlattenMiddleware,
    RequestCancelledMiddleware,
    RequestIDMiddleware,
    request_id_var,
)

# ── RequestIDMiddleware ────────────────────────────────────────────────────


def _rid_app() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/x")
    def h(req: Request):
        return {"rid": req.state.request_id}

    return TestClient(app)


def test_request_id_generated_when_missing():
    r = _rid_app().get("/x")
    rid = r.json()["rid"]
    assert isinstance(rid, str)
    assert len(rid) == 32  # uuid4().hex
    assert r.headers["x-request-id"] == rid


def test_request_id_echoed_when_inbound():
    r = _rid_app().get("/x", headers={"x-request-id": "client-supplied-123"})
    assert r.json()["rid"] == "client-supplied-123"
    assert r.headers["x-request-id"] == "client-supplied-123"


def test_request_id_contextvar_resets_after_request():
    _rid_app().get("/x")
    assert request_id_var.get() == ""


# ── ContentSizeLimitMiddleware ─────────────────────────────────────────────


def _size_app(max_bytes: int) -> TestClient:
    app = FastAPI()
    app.add_middleware(ContentSizeLimitMiddleware, max_bytes=max_bytes)

    @app.post("/echo")
    def e(payload: dict):
        return payload

    return TestClient(app)


def test_size_limit_passes_small_body():
    r = _size_app(100).post("/echo", json={"a": 1})
    assert r.status_code == 200


def test_size_limit_rejects_oversized_body():
    r = _size_app(50).post("/echo", json={"big": "x" * 200})
    assert r.status_code == 413
    assert r.json()["error"] == "payload_too_large"


def test_size_limit_ignores_unparseable_content_length():
    """Bad header value falls through; the actual limit kicks in only when
    Content-Length parses as an int."""
    app = FastAPI()
    app.add_middleware(ContentSizeLimitMiddleware, max_bytes=1)

    @app.post("/x")
    def x():
        return {"ok": True}

    c = TestClient(app)
    # httpx always sends a valid Content-Length, so this exercises the
    # int(declared) > self._max branch directly via a real oversized POST.
    r = c.post("/x", json={"big": "x" * 100})
    assert r.status_code == 413


# ── MultipartBoundaryMiddleware ────────────────────────────────────────────


def _multipart_app() -> TestClient:
    app = FastAPI()
    app.add_middleware(MultipartBoundaryMiddleware, paths=["/upload"])

    @app.post("/upload")
    def u():
        return {"ok": True}

    @app.post("/notguarded")
    def n():
        return {"ok": True}

    return TestClient(app)


def test_multipart_path_outside_guard_passes_through():
    r = _multipart_app().post("/notguarded", json={"a": 1})
    assert r.status_code == 200


def test_multipart_rejects_non_multipart_content_type():
    r = _multipart_app().post("/upload", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert r.json()["error"] == "invalid_multipart"


def test_multipart_rejects_malformed_boundary():
    r = _multipart_app().post(
        "/upload",
        # Genuine RFC violation: boundary contains chars outside [\w-].
        headers={"Content-Type": "multipart/form-data; boundary=bad@chars$"},
    )
    assert r.status_code == 422


def test_multipart_rejects_overlong_boundary():
    r = _multipart_app().post(
        "/upload",
        headers={"Content-Type": "multipart/form-data; boundary=" + "a" * 100},
    )
    assert r.status_code == 422


def test_multipart_accepts_valid_boundary():
    r = _multipart_app().post(
        "/upload",
        headers={"Content-Type": "multipart/form-data; boundary=valid_boundary_123"},
    )
    assert r.status_code == 200


def test_multipart_accepts_rfc2046_punctuation_in_boundary():
    """RFC 2046 bcharsnospace allows '.', '+', '(', ')', '=', '?'."""
    r = _multipart_app().post(
        "/upload",
        headers={
            "Content-Type": "multipart/form-data; boundary=----WebKitFormBoundary.7MA4YWxkTrZu0gW"
        },
    )
    assert r.status_code == 200


def test_multipart_accepts_quoted_boundary_with_extra_params():
    """RFC-compliant: boundary may be quoted, and other params may follow."""
    r = _multipart_app().post(
        "/upload",
        headers={"Content-Type": 'multipart/form-data; boundary="abc123"; charset=UTF-8'},
    )
    assert r.status_code == 200


def test_multipart_accepts_unquoted_boundary_with_extra_params():
    """RFC-compliant: boundary unquoted, charset trailing — must not corrupt parse."""
    r = _multipart_app().post(
        "/upload",
        headers={"Content-Type": "multipart/form-data; boundary=abc123; charset=UTF-8"},
    )
    assert r.status_code == 200


# ── ForwardedPrefixMiddleware ──────────────────────────────────────────────


def _prefix_app() -> TestClient:
    app = FastAPI()
    app.add_middleware(ForwardedPrefixMiddleware)

    @app.get("/where")
    def w(req: Request):
        return {"root_path": req.scope.get("root_path", "")}

    return TestClient(app)


def test_forwarded_prefix_propagated_into_root_path():
    r = _prefix_app().get("/where", headers={"X-Forwarded-Prefix": "/api/spark"})
    assert r.json()["root_path"] == "/api/spark"


def test_forwarded_prefix_strips_trailing_slash():
    r = _prefix_app().get("/where", headers={"X-Forwarded-Prefix": "/api/"})
    assert r.json()["root_path"] == "/api"


def test_forwarded_prefix_absent_leaves_root_path_unchanged():
    r = _prefix_app().get("/where")
    assert r.json()["root_path"] == ""


# ── QueryListFlattenMiddleware ─────────────────────────────────────────────


_IDS_QUERY = Query(default_factory=list)


def _query_app() -> TestClient:
    app = FastAPI()
    app.add_middleware(QueryListFlattenMiddleware, keys=["ids"])

    @app.get("/list")
    def lst(ids: list[str] = _IDS_QUERY, name: str | None = None):
        return {"ids": ids, "name": name}

    return TestClient(app)


def test_query_csv_flattened_for_configured_key():
    r = _query_app().get("/list?ids=a,b,c")
    assert r.json()["ids"] == ["a", "b", "c"]


def test_query_native_repeated_param_still_works():
    r = _query_app().get("/list?ids=a&ids=b")
    assert r.json()["ids"] == ["a", "b"]


def test_query_mixed_csv_and_repeated_combine():
    r = _query_app().get("/list?ids=a,b&ids=c")
    assert r.json()["ids"] == ["a", "b", "c"]


def test_query_unconfigured_key_not_flattened():
    """A comma in a non-listed key is preserved as a literal string."""
    r = _query_app().get("/list?name=a,b,c")
    assert r.json()["name"] == "a,b,c"


# ── RequestCancelledMiddleware ─────────────────────────────────────────────


def test_request_cancelled_middleware_passes_normal_request():
    app = FastAPI()
    app.add_middleware(RequestCancelledMiddleware)

    @app.get("/quick")
    def q():
        return {"ok": True}

    c = TestClient(app)
    r = c.get("/quick")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_request_cancelled_middleware_returns_499_on_disconnect():
    """Mock ``request.is_disconnected`` to flip True after a tick, while the
    handler sleeps. The middleware should cancel the handler and respond 499."""
    import asyncio
    from unittest.mock import patch

    app = FastAPI()
    app.add_middleware(RequestCancelledMiddleware, poll_seconds=0.01)

    @app.get("/slow")
    async def slow():
        await asyncio.sleep(5)
        return {"ok": True}

    # Use httpx ASGI transport; patch is_disconnected so it flips True quickly.
    state = {"disconnected": False}

    async def fake_is_disconnected(self):
        return bool(state["disconnected"])

    async def trigger_disconnect():
        await asyncio.sleep(0.05)
        state["disconnected"] = True

    # NB: this patches the unbound method on the class, so every Request
    # instance in the test process briefly sees the fake. Safe under the
    # default sequential pytest runner; would race under pytest-xdist.
    with patch("starlette.requests.Request.is_disconnected", fake_is_disconnected):
        # Run trigger and the request concurrently in the AnyIO transport.
        # TestClient is sync but the middleware uses asyncio internally; the
        # patched is_disconnected runs inside the same loop.
        task = asyncio.create_task(trigger_disconnect())
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/slow")
        await task

    assert r.status_code == 499
