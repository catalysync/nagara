"""Application settings.

Single Settings class. Env vars are prefixed ``NAGARA_``. Environment is
chosen via ``NAGARA_ENV``, which also selects which ``.env`` file to load
(``.env``, ``.env.test``, ``.env.staging``).

Secrets use ``SecretStr`` — never plain ``str`` — so they're masked in
``repr()`` and tracebacks.

Usage::

    from nagara.config import settings

    if settings.is_production():
        ...
"""

from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from contextvars import ContextVar
from datetime import timedelta
from enum import StrEnum
from typing import Any, Literal

from pydantic import AliasChoices, Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    development = "development"
    test = "test"
    staging = "staging"
    production = "production"


_env = Environment(os.getenv("NAGARA_ENV", Environment.development))
_env_file = {
    Environment.test: ".env.test",
    Environment.staging: ".env.staging",
}.get(_env, ".env")


class Settings(BaseSettings):
    # ── App ─────────────────────────────────────────────────────────────
    ENV: Environment = Environment.development
    APP_NAME: str = "nagara"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"
    TESTING: bool = False

    # ── Security ────────────────────────────────────────────────────────
    # Empty-by-default so verify_settings() can enforce it's set in prod.
    SECRET_KEY: SecretStr = SecretStr("")

    # ── HTTP ────────────────────────────────────────────────────────────
    BASE_URL: str = "http://127.0.0.1:8000"
    FRONTEND_BASE_URL: str = "http://127.0.0.1:3000"
    CORS_ORIGINS: list[str] = []

    # ── Sessions ────────────────────────────────────────────────────────
    USER_SESSION_TTL: timedelta = timedelta(days=31)

    # ── Database ────────────────────────────────────────────────────────
    # Full-URL override. When set, wins over POSTGRES_* parts. Accepts the
    # unprefixed ``DATABASE_URL`` env var too, so operators with an existing
    # Heroku/Render/Supabase URL don't have to rename anything.
    DATABASE_URL: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NAGARA_DATABASE_URL", "DATABASE_URL"),
    )
    POSTGRES_USER: str = "nagara"
    POSTGRES_PWD: SecretStr = SecretStr("nagara")
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nagara"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_POOL_RECYCLE_SECONDS: int = 600
    DATABASE_COMMAND_TIMEOUT_SECONDS: float = 30.0

    model_config = SettingsConfigDict(
        env_prefix="nagara_",
        env_file=_env_file,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Helpers ─────────────────────────────────────────────────────────
    def is_environment(self, envs: set[Environment]) -> bool:
        return self.ENV in envs

    def is_development(self) -> bool:
        return self.is_environment({Environment.development})

    def is_test(self) -> bool:
        return self.is_environment({Environment.test})

    def is_staging(self) -> bool:
        return self.is_environment({Environment.staging})

    def is_production(self) -> bool:
        return self.is_environment({Environment.production})

    def get_postgres_dsn(self, driver: Literal["asyncpg", "psycopg2"] = "asyncpg") -> str:
        # DATABASE_URL (if set) wins over POSTGRES_* parts. Swap or inject the
        # driver so callers always get exactly `postgresql+<driver>://...`.
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith(f"postgresql+{driver}://"):
                return url
            if url.startswith("postgresql+"):
                # Replace whatever driver was specified with the requested one.
                rest = url.split("://", 1)[1]
                return f"postgresql+{driver}://{rest}"
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", f"postgresql+{driver}://", 1)
            return url
        return str(
            PostgresDsn.build(
                scheme=f"postgresql+{driver}",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PWD.get_secret_value(),
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )


def verify_settings(s: Settings) -> None:
    """Fail fast on missing / default production config.

    Call from the FastAPI lifespan so the app refuses to start rather than
    booting with an empty SECRET_KEY or a default DB password.
    """
    if not s.is_production():
        return
    if not s.SECRET_KEY.get_secret_value():
        raise RuntimeError("NAGARA_SECRET_KEY must be set in production")
    if s.POSTGRES_PWD.get_secret_value() == "nagara":
        raise RuntimeError("NAGARA_POSTGRES_PWD must not use the default in production")


settings = Settings()


# ── Scoped overrides ────────────────────
# A ContextVar holds the "current" Settings instance so scoped overrides —
# useful in tests and per-request contexts — can swap it without touching the
# module singleton.

_current: ContextVar[Settings] = ContextVar("nagara_current_settings", default=settings)


def get_current_settings() -> Settings:
    """Return the active Settings, honoring any ``temporary_settings()`` scope."""
    return _current.get()


@contextlib.contextmanager
def temporary_settings(**overrides: Any) -> Iterator[Settings]:
    """Temporarily override settings inside a block.

    Builds a fresh Settings with the given overrides applied on top of the
    currently-active one, swaps the ContextVar, and restores on exit (even on
    exception). Safe to nest.

    Example::

        with temporary_settings(ENV=Environment.production):
            assert get_current_settings().is_production()
    """
    current = _current.get()
    merged = current.model_copy(update=overrides)
    token = _current.set(merged)
    try:
        yield merged
    finally:
        _current.reset(token)
