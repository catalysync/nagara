from unittest.mock import patch

import sentry_sdk

from nagara.exceptions import NotFound
from nagara.sentry import _before_send, configure_sentry, mark_typed_error


def test_configure_sentry_noop_when_dsn_unset(monkeypatch):
    from nagara.config import settings

    monkeypatch.setattr(settings, "SENTRY_DSN", None)
    configure_sentry()
    assert sentry_sdk.get_client().is_active() is False


def test_configure_sentry_initializes_when_dsn_set(monkeypatch):
    from nagara.config import settings

    fake_dsn = "https://abc@o123.ingest.sentry.io/456"
    monkeypatch.setattr(settings, "SENTRY_DSN", fake_dsn)

    with patch("nagara.sentry.sentry_sdk.init") as init_mock:
        configure_sentry()
        init_mock.assert_called_once()
        kwargs = init_mock.call_args.kwargs
        assert kwargs["dsn"] == fake_dsn
        assert kwargs["environment"] == settings.ENV.value
        assert "before_send" in kwargs
        assert kwargs["default_integrations"] is False


def test_before_send_drops_typed_errors():
    event = {"tags": {"nagara_typed_error": "true"}}
    assert _before_send(event, {}) is None  # type: ignore[arg-type]


def test_before_send_keeps_other_events():
    event = {"tags": {"nagara_typed_error": "false"}}
    assert _before_send(event, {}) is event  # type: ignore[arg-type]


def test_before_send_keeps_event_with_no_tags():
    event = {}
    assert _before_send(event, {}) is event  # type: ignore[arg-type]


def test_mark_typed_error_sets_tag_and_context():
    with patch("nagara.sentry.sentry_sdk.set_tag") as tag_mock, patch(
        "nagara.sentry.sentry_sdk.set_context"
    ) as ctx_mock:
        mark_typed_error(NotFound("missing"))
        tag_mock.assert_called_once_with("nagara_typed_error", "true")
        ctx_mock.assert_called_once()
        ctx_args = ctx_mock.call_args.args
        assert ctx_args[0] == "nagara_error"
        assert ctx_args[1]["type"] == "NotFound"
        assert ctx_args[1]["code"] == "not_found"
