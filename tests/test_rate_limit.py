from unittest.mock import Mock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded

from nagara.middleware import RequestIDMiddleware
from nagara.rate_limit import limiter, rate_limit_exceeded_handler


def test_limiter_instance_uses_redis_storage():
    assert limiter.enabled
    assert "redis" in str(getattr(limiter, "_storage_uri", limiter._storage_uri or ""))  # type: ignore[attr-defined]


def test_rate_limit_handler_returns_envelope():
    """Build a fake RateLimitExceeded and run the handler directly."""
    request = Mock(spec=Request)
    request.state = Mock(request_id="rid-123")

    fake_limit = Mock(error_message="2 per 1 minute")
    exc = RateLimitExceeded(fake_limit)
    exc.detail = "2 per 1 minute"  # type: ignore[attr-defined]

    response = rate_limit_exceeded_handler(request, exc)
    import json
    body = json.loads(response.body)
    assert response.status_code == 429
    assert body["error"] == "rate_limit_exceeded"
    assert body["detail"] == "2 per 1 minute"
    assert body["request_id"] == "rid-123"
    assert response.headers["retry-after"] is not None
    assert response.headers["x-request-id"] == "rid-123"


def test_rate_limit_handler_falls_back_request_id_dash():
    """No request_id on state — handler still returns a valid envelope."""
    request = Mock(spec=Request)
    request.state = Mock(spec=[])  # no request_id attribute

    fake_limit = Mock()
    exc = RateLimitExceeded(fake_limit)
    exc.detail = "rate exceeded"  # type: ignore[attr-defined]

    response = rate_limit_exceeded_handler(request, exc)
    import json
    body = json.loads(response.body)
    assert body["request_id"] == "-"


def test_route_decorated_with_limit_returns_429_after_quota():
    """Integration: a decorated route returns 429 once quota exhausted."""
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(RequestIDMiddleware)

    # Use a unique key per test run to avoid Redis state leakage
    import uuid
    test_path = f"/_test_{uuid.uuid4().hex}"

    @app.get(test_path)
    @limiter.limit("2/minute")
    def handler(request: Request):
        return {"ok": True}

    c = TestClient(app)
    statuses = [c.get(test_path).status_code for _ in range(4)]
    # First 2 succeed, next 2 are 429.
    assert statuses[:2] == [200, 200]
    assert statuses[2:] == [429, 429]


def test_429_response_carries_retry_after():
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(RequestIDMiddleware)

    import uuid
    test_path = f"/_test_{uuid.uuid4().hex}"

    @app.get(test_path)
    @limiter.limit("1/minute")
    def handler(request: Request):
        return {"ok": True}

    c = TestClient(app)
    c.get(test_path)
    r = c.get(test_path)
    assert r.status_code == 429
    assert r.headers.get("retry-after") is not None
    assert r.json()["error"] == "rate_limit_exceeded"
