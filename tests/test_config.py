"""Tests for nagara.config."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from nagara.config import Environment, Settings, verify_settings


def test_environment_enum_values():
    assert {e.value for e in Environment} == {"development", "test", "staging", "production"}


def test_is_production_helper():
    s = Settings(ENV=Environment.production)
    assert s.is_production()
    assert not s.is_development()


def test_is_development_helper():
    s = Settings(ENV=Environment.development)
    assert s.is_development()
    assert not s.is_production()


def test_postgres_dsn_default_driver_is_asyncpg():
    s = Settings(
        POSTGRES_USER="alice",
        POSTGRES_PWD=SecretStr("p"),
        POSTGRES_HOST="h",
        POSTGRES_PORT=1,
        POSTGRES_DB="d",
    )
    assert s.get_postgres_dsn() == "postgresql+asyncpg://alice:p@h:1/d"


def test_postgres_dsn_sync_driver():
    s = Settings(
        POSTGRES_USER="alice",
        POSTGRES_PWD=SecretStr("p"),
        POSTGRES_HOST="h",
        POSTGRES_PORT=1,
        POSTGRES_DB="d",
    )
    assert s.get_postgres_dsn("psycopg2") == "postgresql+psycopg2://alice:p@h:1/d"


def test_verify_settings_noop_in_development():
    s = Settings(ENV=Environment.development)
    verify_settings(s)  # does not raise


def test_verify_settings_rejects_empty_secret_in_production():
    s = Settings(ENV=Environment.production, SECRET_KEY=SecretStr(""))
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        verify_settings(s)


def test_verify_settings_rejects_default_pg_pwd_in_production():
    s = Settings(
        ENV=Environment.production,
        SECRET_KEY=SecretStr("real"),
        POSTGRES_PWD=SecretStr("nagara"),
    )
    with pytest.raises(RuntimeError, match="POSTGRES_PWD"):
        verify_settings(s)


def test_verify_settings_passes_when_prod_configured():
    s = Settings(
        ENV=Environment.production,
        SECRET_KEY=SecretStr("real"),
        POSTGRES_PWD=SecretStr("real-pg"),
    )
    verify_settings(s)  # does not raise


def test_secretstr_masks_repr():
    s = Settings(POSTGRES_PWD=SecretStr("nagara"))
    assert "nagara" not in repr(s.POSTGRES_PWD)
