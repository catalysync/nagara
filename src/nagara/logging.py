"""Logging configuration. Pretty colored console in dev, JSON in prod;
structlog under the hood so contextvars (request_id, user_id when bound)
auto-merge into every record without a per-field LogFilter."""

from __future__ import annotations

import logging
import logging.config
from typing import Any

import structlog

from nagara.config import settings

Logger = structlog.stdlib.BoundLogger


# Loggers from third-party libs that emit through stdlib `logging` and
# would otherwise use their own format. Routing them through our pipeline
# means uvicorn / sqlalchemy / etc. emit JSON in prod with the same shape
# as our own logs.
_THIRD_PARTY_LOGGERS = ["uvicorn", "uvicorn.access", "uvicorn.error", "sqlalchemy"]


def _shared_processors() -> list[Any]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.StackInfoRenderer(),
    ]


def _renderer() -> Any:
    if settings.is_development() or settings.is_test():
        return structlog.dev.ConsoleRenderer(colors=True)
    return structlog.processors.JSONRenderer()


def configure_logging() -> None:
    """Idempotent — safe to call multiple times. Wires both stdlib `logging`
    and structlog so a `logging.getLogger(__name__).info(...)` call from
    third-party code emits through the same renderer/processors as our own
    structlog calls."""
    level = settings.LOG_LEVEL

    logging.config.dictConfig(
        {
            "version": 1,
            # Loggers may have been created during config import (pydantic,
            # uv, third-party libs) before configure_logging() runs. Disabling
            # them silently drops their output.
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        _renderer(),
                    ],
                    "foreign_pre_chain": [
                        *_shared_processors(),
                        structlog.stdlib.ExtraAdder(),
                    ],
                },
            },
            "handlers": {
                "default": {
                    "level": level,
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": level,
                    "propagate": False,
                },
                **{name: {"handlers": [], "propagate": True} for name in _THIRD_PARTY_LOGGERS},
            },
        }
    )

    structlog.configure_once(
        processors=[
            *_shared_processors(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
