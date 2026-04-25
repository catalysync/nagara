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
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field, PostgresDsn, SecretStr, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from nagara.layered import deep_merge, load_pyproject_config, load_toml_config
from nagara.profiles import load_profiles

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


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


# ── Layered TOML source ────────────────────────────────────────────────────
# Merges three optional files into one source tier that sits below env/.env
# but above field defaults:
#
#   pyproject.toml     [tool.nagara]                    — committed, repo-wide
#   user config.toml   ~/.config/nagara/config.toml     — per-operator
#   profiles.toml      ~/.config/nagara/profiles.toml   — named profiles
#
# The active profile is chosen by (1) $NAGARA_PROFILE, (2) ``active = "..."``
# inside profiles.toml, otherwise no profile overrides apply. Env-var hooks
# (``NAGARA_PYPROJECT``, ``NAGARA_USER_CONFIG``, ``NAGARA_PROFILES``) let
# tests + deployments retarget the discovery paths without a file rename.


def _pyproject_path() -> Path:
    return Path(os.environ.get("NAGARA_PYPROJECT", "pyproject.toml"))


def _user_config_path() -> Path:
    override = os.environ.get("NAGARA_USER_CONFIG")
    if override:
        return Path(override)
    return Path.home() / ".config" / "nagara" / "config.toml"


def _profiles_path() -> Path:
    override = os.environ.get("NAGARA_PROFILES")
    if override:
        return Path(override)
    return Path.home() / ".config" / "nagara" / "profiles.toml"


class TomlLayeredSource(PydanticBaseSettingsSource):
    """pydantic-settings source that merges pyproject + user + profile TOML.

    Priority inside this source (highest wins):
        active profile section > user config.toml > pyproject [tool.nagara]

    The merged dict feeds into :class:`Settings` below env vars and .env
    files, so a value in ``NAGARA_POSTGRES_HOST`` still beats a value in
    ``config.toml``.
    """

    def _load_raw(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        merged = deep_merge(merged, load_pyproject_config(_pyproject_path()))
        merged = deep_merge(merged, load_toml_config(_user_config_path()))

        store = load_profiles(_profiles_path())
        active = os.environ.get("NAGARA_PROFILE") or store.active
        if active is not None:
            try:
                profile = store.get(active)
            except KeyError:
                profile = None
            if profile is not None:
                merged = deep_merge(merged, profile.overrides)

        # Lowercase the keys so case-insensitive matching against field names
        # works regardless of how TOML authors capitalize them.
        return {k.lower(): v for k, v in merged.items()}

    def get_field_value(
        self,
        field: FieldInfo,  # noqa: ARG002 — required by PydanticBaseSettingsSource ABC
        field_name: str,
    ) -> tuple[Any, str, bool]:
        data = self._load_raw()
        value = data.get(field_name.lower())
        return (
            value,
            field_name,
            value is not None and not isinstance(value, str | int | float | bool),
        )

    def __call__(self) -> dict[str, Any]:
        # Return a dict keyed by the exact field names so pydantic-settings
        # merges it cleanly with the other sources. Missing fields are
        # simply absent (falls through to lower-priority sources or default).
        raw = self._load_raw()
        out: dict[str, Any] = {}
        for field_name in self.settings_cls.model_fields:
            lower = field_name.lower()
            if lower in raw:
                out[field_name] = raw[lower]
        return out


class Settings(BaseSettings):
    # ── App ─────────────────────────────────────────────────────────────
    ENV: Environment = Field(
        default=Environment.development,
        description="Deployment environment. Drives .env file selection and prod-only guardrails.",
    )
    APP_NAME: str = Field(default="nagara", description="Display name in API docs, logs, metrics.")
    APP_VERSION: str = Field(
        default="0.1.0", description="Version string surfaced in /openapi.json."
    )
    LOG_LEVEL: LogLevel | None = Field(
        default=None,
        description=(
            "Python logging level. When unset, derived from ENV: DEBUG in development, "
            "INFO everywhere else."
        ),
    )
    TESTING: bool = Field(default=False, description="Test-only flag. Don't set in production.")

    # ── Security ────────────────────────────────────────────────────────
    SECRET_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Signs JWTs + session cookies. Must be set in production (≥32 chars).",
    )

    # ── HTTP ────────────────────────────────────────────────────────────
    BASE_URL: str = Field(
        default="http://127.0.0.1:8000",
        description="Public backend URL — used when building absolute links in emails, webhooks.",
    )
    FRONTEND_BASE_URL: str = Field(
        default="http://127.0.0.1:3000",
        description="Public frontend URL — used for post-auth redirects.",
    )
    CORS_ORIGINS: list[str] = Field(
        default_factory=list,
        description="Allowed CORS origins. Empty list disables cross-origin requests.",
    )
    CORS_ORIGIN_REGEX: str | None = Field(
        default=None,
        description="Regex pattern matched against the request Origin in addition to CORS_ORIGINS. Use for ephemeral preview hosts.",
    )

    # ── Sessions ────────────────────────────────────────────────────────
    USER_SESSION_TTL: timedelta = Field(
        default=timedelta(days=31),
        description="How long a user session lasts before forcing re-auth.",
    )

    # ── Database ────────────────────────────────────────────────────────
    DATABASE_URL: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NAGARA_DATABASE_URL", "DATABASE_URL"),
        description=(
            "Full DSN override. When set, wins over POSTGRES_* parts. Accepts the "
            "unprefixed DATABASE_URL env var too."
        ),
    )
    POSTGRES_USER: str = Field(default="nagara", description="Postgres username.")
    POSTGRES_PWD: SecretStr = Field(default=SecretStr("nagara"), description="Postgres password.")
    POSTGRES_HOST: str = Field(default="127.0.0.1", description="Postgres host.")
    POSTGRES_PORT: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="Postgres port. Must be a valid TCP port.",
    )
    POSTGRES_DB: str = Field(default="nagara", description="Postgres database name.")
    DATABASE_POOL_SIZE: int = Field(
        default=5,
        ge=1,
        le=500,
        description="SQLAlchemy connection pool size. Tune per replica.",
    )
    DATABASE_POOL_RECYCLE_SECONDS: int = Field(
        default=600,
        ge=1,
        description="Seconds before a pooled connection is recycled. Guards against stale conns.",
    )
    DATABASE_COMMAND_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        gt=0,
        description="Per-query timeout. 0 is not a valid value — prevents runaway queries.",
    )

    # ── Redis ───────────────────────────────────────────────────────────
    REDIS_URL: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis DSN. Used by the rate limiter and any future cache/queue.",
    )

    # ── Observability ───────────────────────────────────────────────────
    SENTRY_DSN: str | None = Field(
        default=None,
        description="Sentry DSN for error reporting. Unset disables Sentry entirely.",
    )
    RELEASE_VERSION: str = Field(
        default="dev",
        description="Build version stamped into Sentry events and OpenAPI. Set by CI.",
    )

    # ── Validators ─────────────────────────────────────────────────────
    @field_validator("LOG_LEVEL", mode="after")
    @classmethod
    def _default_log_level_from_env(cls, v: str | None, info) -> str:  # noqa: ANN001
        """Fill ``LOG_LEVEL`` when unset: DEBUG in development, INFO otherwise."""
        if v is not None:
            return v
        env = info.data.get("ENV", Environment.development)
        return "DEBUG" if env == Environment.development else "INFO"

    # Template for future deprecations — when a setting is renamed, keep a
    # validator on the new name that watches for the old env var and emits a
    # warning. Example (commented, no active deprecation right now)::
    #
    #     @field_validator("POSTGRES_PWD", mode="before")
    #     @classmethod
    #     def _warn_old_db_password(cls, v):
    #         if os.environ.get("NAGARA_DB_PASSWORD") is not None:
    #             import warnings
    #             warnings.warn(
    #                 "NAGARA_DB_PASSWORD is deprecated — rename to NAGARA_POSTGRES_PWD",
    #                 DeprecationWarning,
    #                 stacklevel=2,
    #             )
    #             return os.environ["NAGARA_DB_PASSWORD"]
    #         return v

    model_config = SettingsConfigDict(
        env_prefix="nagara_",
        env_file=_env_file,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Read Docker / k8s mounted secrets (``/run/secrets/NAGARA_SECRET_KEY``,
        # ``/run/secrets/NAGARA_POSTGRES_PWD``, ...). Pydantic-settings warns
        # if the dir doesn't exist, so we only wire it up when it does.
        secrets_dir=(
            os.environ.get("NAGARA_SECRETS_DIR")
            or ("/run/secrets" if Path("/run/secrets").is_dir() else None)
        ),
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Highest priority first. The TOML layer sits below env + .env so a
        # deployment env var still wins, but above file-secret defaults so
        # an operator TOML config is respected.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlLayeredSource(settings_cls),
            file_secret_settings,
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

    def safe_dump(self, *, include_secrets: bool = False) -> dict[str, Any]:
        """Serialize to a plain dict suitable for API responses or debug views.

        SecretStr fields are replaced with ``"***"`` unless ``include_secrets=True``,
        in which case they're unwrapped to their real string value.
        Non-JSON-serializable types (timedelta, etc.) stay as-is — pass the result
        through ``json.dumps(..., default=str)`` if you need a JSON string.
        """
        data = self.model_dump(mode="python")
        for name in type(self).model_fields:
            attr = getattr(self, name, None)
            if isinstance(attr, SecretStr):
                data[name] = attr.get_secret_value() if include_secrets else "***"
        return data

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
