from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from nagara.config import settings

if TYPE_CHECKING:
    from sentry_sdk._types import Event, Hint


def _before_send(event: Event, hint: Hint) -> Event | None:
    tags = event.get("tags") or {}
    if tags.get("nagara_typed_error") == "true":
        return None
    return event


def configure_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV.value,
        release=settings.RELEASE_VERSION,
        send_default_pii=False,
        before_send=_before_send,
        default_integrations=False,
        auto_enabling_integrations=False,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )


def mark_typed_error(exc: BaseException) -> None:
    sentry_sdk.set_tag("nagara_typed_error", "true")
    sentry_sdk.set_context(
        "nagara_error",
        {"type": type(exc).__name__, "code": getattr(exc, "error_code", None)},
    )
