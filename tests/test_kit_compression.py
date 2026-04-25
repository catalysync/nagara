import gzip
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from nagara.kit.compression import gzip_json_response


def test_gzip_response_headers_set_correctly():
    app = FastAPI()

    @app.get("/x")
    def h():
        return gzip_json_response({"a": 1, "b": [1, 2, 3]})

    c = TestClient(app)
    r = c.get("/x")
    assert r.status_code == 200
    assert r.headers["content-encoding"] == "gzip"
    assert r.headers["vary"] == "Accept-Encoding"
    # httpx TestClient auto-decompresses; the body should round-trip.
    assert r.json() == {"a": 1, "b": [1, 2, 3]}


def test_gzip_response_body_actually_compressed():
    """Call the helper directly to inspect the raw wire bytes (TestClient
    auto-decompresses regardless of Accept-Encoding)."""
    payload = {"rows": [{"i": i, "name": "name_" + str(i)} for i in range(500)]}
    response = gzip_json_response(payload)
    raw = response.body
    decompressed = gzip.decompress(raw)
    assert json.loads(decompressed) == payload
    # Compressed should be meaningfully smaller than uncompressed JSON.
    assert len(raw) < len(json.dumps(payload).encode()) // 2
    assert response.headers["content-encoding"] == "gzip"


def test_gzip_response_handles_status_code_override():
    app = FastAPI()

    @app.get("/x")
    def h():
        return gzip_json_response({"created": True}, status_code=201)

    c = TestClient(app)
    r = c.get("/x")
    assert r.status_code == 201
    assert r.json() == {"created": True}


def test_gzip_response_serializes_pydantic_via_jsonable_encoder():
    from datetime import UTC, datetime

    from nagara.kit.schemas import Schema

    class _Row(Schema):
        when: datetime

    app = FastAPI()
    when = datetime.now(UTC)

    @app.get("/x")
    def h():
        return gzip_json_response(_Row(when=when))

    c = TestClient(app)
    body = c.get("/x").json()
    # datetime should be ISO-encoded
    assert isinstance(body["when"], str)
    assert "T" in body["when"]
