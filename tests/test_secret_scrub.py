"""Tests for the logging-level secret scrubber."""

from __future__ import annotations

import logging

import pytest
from pydantic import SecretStr

from nagara.config import Settings
from nagara.secrets import SecretScrubber, install_secret_scrubber


@pytest.fixture
def logger_with_scrubber():
    """Yields (logger, scrubber, captured_list) with scrubber installed."""
    records: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(self.format(record))

    logger = logging.getLogger(f"test.scrubber.{id(records)}")
    logger.setLevel(logging.DEBUG)
    handler = _Capture()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    scrubber = SecretScrubber()
    logger.addFilter(scrubber)
    try:
        yield logger, scrubber, records
    finally:
        logger.removeFilter(scrubber)
        logger.removeHandler(handler)


def test_scrubber_masks_literal_secret(logger_with_scrubber):
    logger, scrubber, records = logger_with_scrubber
    scrubber.add("super-s3cret")
    logger.warning("DB connected with password super-s3cret")
    assert "super-s3cret" not in records[0]
    assert "***" in records[0]


def test_scrubber_masks_via_format_args(logger_with_scrubber):
    logger, scrubber, records = logger_with_scrubber
    scrubber.add("leaky-token")
    logger.error("oauth failed: %s", "leaky-token")
    assert "leaky-token" not in records[0]
    assert "***" in records[0]


def test_scrubber_does_not_mask_unregistered_strings(logger_with_scrubber):
    logger, scrubber, records = logger_with_scrubber
    scrubber.add("secret-a")
    logger.info("this message contains secret-b which is fine")
    assert "secret-b" in records[0]


def test_scrubber_ignores_empty_strings(logger_with_scrubber):
    """Empty or whitespace secrets must never cause global wildcard matches."""
    logger, scrubber, records = logger_with_scrubber
    scrubber.add("")
    scrubber.add("   ")
    logger.info("hello world")
    assert records[0] == "hello world"


def test_install_secret_scrubber_collects_settings_secretstr_fields():
    s = Settings(POSTGRES_PWD=SecretStr("discovered-pwd"), SECRET_KEY=SecretStr("sk-discovered"))
    scrubber = install_secret_scrubber(settings=s)
    try:
        assert "discovered-pwd" in scrubber
        assert "sk-discovered" in scrubber
    finally:
        scrubber.uninstall()


def test_install_secret_scrubber_attaches_to_root_logger():
    s = Settings(POSTGRES_PWD=SecretStr("root-pwd"))
    scrubber = install_secret_scrubber(settings=s)
    try:
        assert scrubber in logging.getLogger().filters
    finally:
        scrubber.uninstall()
        assert scrubber not in logging.getLogger().filters


def test_install_accepts_extra_secrets():
    scrubber = install_secret_scrubber(secrets=["extra-1", "extra-2"])
    try:
        assert "extra-1" in scrubber
        assert "extra-2" in scrubber
    finally:
        scrubber.uninstall()
