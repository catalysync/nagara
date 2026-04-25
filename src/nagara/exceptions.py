from __future__ import annotations

import re
from typing import Any


def _camel_to_snake(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s).lower()


class NagaraError(Exception):
    """Base for any exception that should turn into a typed HTTP response.

    ``error_code`` is auto-derived from the subclass name (snake_case) at
    class-creation time. Subclasses that want a stable wire code decoupled
    from the Python class name (so a rename doesn't break clients) can
    override by setting ``error_code`` explicitly.
    """

    status_code: int = 500
    error_code: str = "internal_error"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if "error_code" not in cls.__dict__:
            cls.error_code = _camel_to_snake(cls.__name__)

    def __init__(
        self,
        message: str,
        *,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.headers = headers or {}
        self.extra = extra or {}


class NotFound(NagaraError):
    status_code = 404


class Forbidden(NagaraError):
    status_code = 403


class Unauthorized(NagaraError):
    status_code = 401


class Conflict(NagaraError):
    status_code = 409


class ValidationFailed(NagaraError):
    status_code = 422
