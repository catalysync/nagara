"""Alembic environment.

Pulls the database URL from ``nagara.config.settings`` so we never duplicate
the DSN-assembly logic. Imports ``nagara.db.metadata`` (registered later by
each model module) for autogenerate.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Models import their Base / register themselves on the metadata when their
# package is imported. Importing the db module triggers that registration.
from nagara import db  # noqa: F401  — side-effect import
from nagara.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the *sync* DSN (psycopg2) for migrations. Async drivers don't play nice
# with Alembic's offline-mode SQL emission. ``%``-escape so a literal ``%``
# in a password (or any other DSN component) isn't read as an alembic.ini
# interpolation marker — Alembic feeds the DSN through configparser.
config.set_main_option(
    "sqlalchemy.url",
    settings.get_postgres_dsn("psycopg2").replace("%", "%%"),
)

target_metadata = db.metadata


def include_object(obj, name, type_, reflected, compare_to):
    """Skip objects flagged ``info={"skip_autogenerate": True}``.

    Lets us declare tables/indexes/views in the metadata that the app reads
    or joins against but that are managed outside alembic — Postgres
    extension tables, partitions handled by triggers, etc. Without this,
    autogenerate would emit DROP statements for them on every revision.
    """
    if type_ in ("table", "index") and getattr(obj, "info", None):
        if obj.info.get("skip_autogenerate"):
            return False
    return True


def run_migrations_offline() -> None:
    """Generate SQL for migrations without connecting to the database."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
