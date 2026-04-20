"""Tests for validation aliases — legacy / unprefixed env var compat."""

from __future__ import annotations

from nagara.config import Settings


def _isolated_env(monkeypatch):
    """Clear DATABASE_URL-related env vars so tests are hermetic."""
    for key in ("NAGARA_DATABASE_URL", "DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)


def test_database_url_accepts_unprefixed_env_var(monkeypatch):
    """An operator's existing `DATABASE_URL` env var works without renaming."""
    _isolated_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h:5432/db")
    s = Settings()
    assert s.DATABASE_URL == "postgresql://u:p@h:5432/db"


def test_database_url_accepts_prefixed_env_var(monkeypatch):
    _isolated_env(monkeypatch)
    monkeypatch.setenv("NAGARA_DATABASE_URL", "postgresql://prefixed@h/db")
    s = Settings()
    assert "prefixed" in (s.DATABASE_URL or "")


def test_database_url_prefixed_wins_over_unprefixed(monkeypatch):
    """When both are set, the NAGARA_-prefixed value takes precedence."""
    _isolated_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unprefixed@h/db")
    monkeypatch.setenv("NAGARA_DATABASE_URL", "postgresql://prefixed@h/db")
    s = Settings()
    assert "prefixed" in (s.DATABASE_URL or "")
    assert "unprefixed" not in (s.DATABASE_URL or "")


def test_database_url_default_is_none_when_unset(monkeypatch):
    _isolated_env(monkeypatch)
    s = Settings()
    assert s.DATABASE_URL is None


def test_get_postgres_dsn_uses_database_url_when_set():
    """If DATABASE_URL is supplied, the DSN comes from it, ignoring POSTGRES_* parts."""
    s = Settings(DATABASE_URL="postgresql://url_user:url_pwd@url_host:9999/url_db")
    dsn = s.get_postgres_dsn()
    assert dsn == "postgresql+asyncpg://url_user:url_pwd@url_host:9999/url_db"


def test_get_postgres_dsn_adds_driver_prefix_if_missing():
    """DATABASE_URL with 'postgresql://' gets the +asyncpg driver added."""
    s = Settings(DATABASE_URL="postgresql://u:p@h:1/d")
    assert s.get_postgres_dsn("psycopg2") == "postgresql+psycopg2://u:p@h:1/d"


def test_get_postgres_dsn_keeps_driver_if_already_specified():
    """DATABASE_URL already specifying a driver is returned as-is."""
    s = Settings(DATABASE_URL="postgresql+asyncpg://u:p@h:1/d")
    assert s.get_postgres_dsn("asyncpg") == "postgresql+asyncpg://u:p@h:1/d"
