"""nagara — your operating system for data."""

from importlib.metadata import PackageNotFoundError, version

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
)
from nagara.lifespan import on_shutdown, on_startup
from nagara.routing import APIRouter, APITag

try:
    __version__ = version("nagara")
except PackageNotFoundError:
    __version__ = "0.0.0+local"

__all__ = [
    "APIRouter",
    "APITag",
    "BadRequest",
    "Conflict",
    "FieldError",
    "Forbidden",
    "Gone",
    "InternalServerError",
    "NagaraError",
    "NotFound",
    "TaskError",
    "Unauthorized",
    "ValidationFailed",
    "__version__",
    "on_shutdown",
    "on_startup",
]
