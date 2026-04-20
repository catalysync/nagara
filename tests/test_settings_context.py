"""Tests for the scoped settings override contextmanager."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from nagara.config import Environment, get_current_settings, temporary_settings


def test_temporary_settings_overrides_within_block():
    with temporary_settings(ENV=Environment.production):
        assert get_current_settings().is_production()


def test_temporary_settings_reverts_after_block():
    before = get_current_settings().ENV
    with temporary_settings(ENV=Environment.production):
        pass
    assert before == get_current_settings().ENV


def test_temporary_settings_nests_correctly():
    """Nested blocks override and correctly restore each layer."""
    with temporary_settings(ENV=Environment.staging):
        assert get_current_settings().is_staging()
        with temporary_settings(ENV=Environment.production):
            assert get_current_settings().is_production()
        assert get_current_settings().is_staging()


def test_temporary_settings_overrides_multiple_fields():
    with temporary_settings(ENV=Environment.production, SECRET_KEY=SecretStr("test-key")):
        s = get_current_settings()
        assert s.is_production()
        assert s.SECRET_KEY.get_secret_value() == "test-key"


def test_temporary_settings_restores_on_exception():
    before = get_current_settings().ENV
    with pytest.raises(ValueError), temporary_settings(ENV=Environment.production):
        raise ValueError("boom")
    assert before == get_current_settings().ENV


def test_get_current_settings_returns_module_singleton_by_default():
    """Outside any override block, returns the module-level ``settings``."""
    from nagara.config import settings

    assert get_current_settings() is settings
