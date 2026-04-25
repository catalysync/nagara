from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, create_model


def _camel_to_snake(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


class FieldError(BaseModel):
    """A single field-level validation error.

    Mirrors Pydantic's per-error shape so a service-raised validation error
    is structurally identical to one FastAPI emits for body validation.
    """

    loc: tuple[int | str, ...]
    msg: str
    type: str
    input: Any | None = None


class NagaraError(Exception):
    """Base for any exception that should turn into a typed HTTP response.

    ``error_code`` is auto-derived from the subclass name (snake_case) at
    class-creation time. Subclasses that want a stable wire code decoupled
    from the Python class name can override ``error_code`` explicitly.
    """

    status_code: int = 500
    error_code: str = "internal_error"
    default_message: str = "internal error"

    _schema_cache: ClassVar[type[BaseModel] | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "error_code" not in cls.__dict__:
            cls.error_code = _camel_to_snake(cls.__name__)
        # Force per-subclass schema cache so subclasses don't reuse
        # the parent's generated model.
        cls._schema_cache = None

    def __init__(
        self,
        message: str | None = None,
        *,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        message = message or self.default_message
        super().__init__(message)
        self.message = message
        self.headers = headers or {}
        self.extra = extra or {}

    @classmethod
    def schema(cls) -> type[BaseModel]:
        """A Pydantic model describing this exception's HTTP response shape.

        Endpoints declare ``responses={cls.status_code: {"model": cls.schema()}}``
        on the route decorator; the model surfaces in OpenAPI with ``error``
        as a Literal of the wire code. Generated TS clients then type-narrow
        on ``response.error`` as a discriminated union.
        """
        if cls._schema_cache is not None:
            return cls._schema_cache

        error_literal = Literal[cls.error_code]  # type: ignore[valid-type]
        cls._schema_cache = create_model(
            cls.__name__,
            error=(error_literal, Field(examples=[cls.error_code])),
            detail=(str, Field(examples=[cls.default_message])),
            request_id=(str, Field(examples=["abc123def456"])),
        )
        return cls._schema_cache


class BadRequest(NagaraError):
    status_code = 400
    default_message = "bad request"


class Unauthorized(NagaraError):
    status_code = 401
    default_message = "unauthorized"

    def __init__(
        self,
        message: str | None = None,
        *,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
        realm: str = "nagara",
    ) -> None:
        merged = {"WWW-Authenticate": f'Bearer realm="{realm}"'}
        if headers:
            merged.update(headers)
        super().__init__(message, headers=merged, extra=extra)


class Forbidden(NagaraError):
    status_code = 403
    default_message = "forbidden"


class NotFound(NagaraError):
    status_code = 404
    default_message = "not found"


class Conflict(NagaraError):
    status_code = 409
    default_message = "already exists"


class ValidationFailed(NagaraError):
    """422 with optional per-field structured errors.

    Service code can raise field-level validation errors with the same wire
    shape Pydantic emits for body validation, so a frontend's form library
    handles both the same way.
    """

    status_code = 422
    default_message = "validation failed"

    def __init__(
        self,
        message: str | None = None,
        *,
        errors: Sequence[FieldError | dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.errors: list[FieldError] = [
            e if isinstance(e, FieldError) else FieldError(**e) for e in (errors or [])
        ]
        super().__init__(message, headers=headers, extra=extra)


class Gone(NagaraError):
    status_code = 410
    default_message = "gone"


class InternalServerError(NagaraError):
    status_code = 500
    default_message = "internal server error"


class TaskError(NagaraError):
    """Marker base for errors raised inside background tasks / CLI / scripts.

    A ``TaskError`` leaking into the HTTP path is itself a bug — task code
    should catch and surface them via job status, not return them to an
    HTTP client.
    """
