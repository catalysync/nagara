import pytest
from fastapi.testclient import TestClient

from nagara.exceptions import (
    BadRequest,
    Conflict,
    FieldError,
    Forbidden,
    Gone,
    InternalServerError,
    NagaraError,
    NotFound,
    TaskError,
    Unauthorized,
    ValidationFailed,
    _camel_to_snake,
)

# ── _camel_to_snake helper ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name,expected",
    [
        ("NotFound", "not_found"),
        ("OrgNotFound", "org_not_found"),
        ("MFANotEnabled", "mfa_not_enabled"),
        ("Plain", "plain"),
        ("HTTPError", "http_error"),
        ("AlreadyDoneTask", "already_done_task"),
    ],
)
def test_camel_to_snake_handles_acronyms(name, expected):
    assert _camel_to_snake(name) == expected


# ── error_code auto-derivation ──────────────────────────────────────────────


def test_base_class_has_internal_error_code():
    assert NagaraError.error_code == "internal_error"


@pytest.mark.parametrize(
    "cls,expected_code,expected_status",
    [
        (BadRequest, "bad_request", 400),
        (Unauthorized, "unauthorized", 401),
        (Forbidden, "forbidden", 403),
        (NotFound, "not_found", 404),
        (Conflict, "conflict", 409),
        (Gone, "gone", 410),
        (ValidationFailed, "validation_failed", 422),
        (InternalServerError, "internal_server_error", 500),
        (TaskError, "task_error", 500),
    ],
)
def test_subclass_codes_and_status(cls, expected_code, expected_status):
    assert cls.error_code == expected_code
    assert cls.status_code == expected_status


def test_subclass_can_override_error_code_explicitly():
    class WeirdName(NagaraError):
        error_code = "totally_custom"

    assert WeirdName.error_code == "totally_custom"


def test_user_subclass_auto_derives_from_class_name():
    class OrgNotFound(NotFound):
        pass

    assert OrgNotFound.error_code == "org_not_found"
    assert OrgNotFound.status_code == 404


# ── Default messages ────────────────────────────────────────────────────────


def test_default_messages_apply_when_unspecified():
    assert NotFound().message == "not found"
    assert BadRequest().message == "bad request"
    assert Conflict().message == "already exists"
    assert Unauthorized().message == "unauthorized"


def test_explicit_message_overrides_default():
    assert NotFound("custom").message == "custom"


# ── Unauthorized auto-WWW-Authenticate ──────────────────────────────────────


def test_unauthorized_adds_www_authenticate_header():
    e = Unauthorized()
    assert e.headers["WWW-Authenticate"].startswith('Bearer realm="')


def test_unauthorized_custom_realm():
    e = Unauthorized(realm="api.nagara.com")
    assert e.headers["WWW-Authenticate"] == 'Bearer realm="api.nagara.com"'


def test_unauthorized_caller_headers_merged():
    e = Unauthorized(headers={"X-Custom": "val"})
    assert e.headers["X-Custom"] == "val"
    assert "WWW-Authenticate" in e.headers


# ── ValidationFailed structured errors ──────────────────────────────────────


def test_validation_failed_accepts_dict_errors():
    e = ValidationFailed(
        errors=[
            {"loc": ("body", "email"), "msg": "already taken", "type": "value_error.unique"},
        ]
    )
    assert len(e.errors) == 1
    assert isinstance(e.errors[0], FieldError)
    assert e.errors[0].loc == ("body", "email")


def test_validation_failed_accepts_field_error_instances():
    fe = FieldError(loc=("body", "x"), msg="bad", type="value_error", input=None)
    e = ValidationFailed(errors=[fe])
    assert e.errors == [fe]


def test_validation_failed_no_errors_defaults_to_empty():
    e = ValidationFailed()
    assert e.errors == []


# ── schema() classmethod for OpenAPI ───────────────────────────────────────


def test_schema_returns_pydantic_model():
    schema = NotFound.schema()
    json_schema = schema.model_json_schema()
    assert json_schema["properties"]["error"]["const"] == "not_found"
    assert "detail" in json_schema["properties"]
    assert "request_id" in json_schema["properties"]


def test_schema_per_subclass_isolation():
    """Each subclass has its own schema cached, not the parent's."""
    nf_schema = NotFound.schema()
    bf_schema = BadRequest.schema()
    assert nf_schema is not bf_schema
    assert nf_schema.model_json_schema()["properties"]["error"]["const"] == "not_found"
    assert bf_schema.model_json_schema()["properties"]["error"]["const"] == "bad_request"


def test_schema_idempotent():
    s1 = NotFound.schema()
    s2 = NotFound.schema()
    assert s1 is s2


# ── extra payload ───────────────────────────────────────────────────────────


def test_extra_attached_to_exception():
    e = NotFound("missing", extra={"org_id": "abc"})
    assert e.extra == {"org_id": "abc"}


def test_extra_defaults_to_empty_dict():
    assert NotFound().extra == {}


# ── Integration with FastAPI handler ────────────────────────────────────────


def _build_app() -> TestClient:
    """Use the real `create_app()` factory so we exercise the production
    NagaraError handler — including request_id, mark_typed_error, and
    header merge order."""
    from nagara.main import create_app

    app = create_app()

    @app.get("/nf")
    def nf():
        raise NotFound("missing thing", extra={"thing_id": "123"})

    @app.get("/vf")
    def vf():
        raise ValidationFailed(
            errors=[{"loc": ("body", "name"), "msg": "too short", "type": "value_error.too_short"}]
        )

    @app.get("/auth")
    def au():
        raise Unauthorized()

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    return TestClient(app)


def test_envelope_shape_for_not_found():
    r = _build_app().get("/nf")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "not_found"
    assert body["detail"] == "missing thing"
    assert body["extra"] == {"thing_id": "123"}
    assert body["request_id"] == r.headers["x-request-id"]


def test_envelope_includes_errors_for_validation_failed():
    r = _build_app().get("/vf")
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "validation_failed"
    assert body["errors"][0]["loc"] == ["body", "name"]
    assert body["request_id"]


def test_envelope_includes_www_authenticate_for_401():
    r = _build_app().get("/auth")
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Bearer")
    assert r.headers["x-request-id"]


def test_unhandled_exception_returns_internal_envelope():
    """TestClient re-raises by default; raise_server_exceptions=False lets
    the production handler run so we can assert its envelope shape."""
    from nagara.main import create_app

    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["error"] == "internal_error"
    assert "RuntimeError" in body["detail"]
    assert body["request_id"] == r.headers["x-request-id"]
