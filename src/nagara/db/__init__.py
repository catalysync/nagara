"""Database engine, session factory, and SQLAlchemy declarative base.

Models live in submodules (``nagara.org.model``, etc.) and register
themselves on ``Base.metadata`` at import time. Alembic's ``env.py`` imports
this package, then iterates ``metadata.tables`` for autogenerate.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention so generated index/constraint names are stable + readable.
_naming = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_N_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    """Common declarative base. Every model subclasses this."""

    metadata = MetaData(naming_convention=_naming)


# Re-exported for Alembic's env.py.
metadata = Base.metadata


from nagara.db.mixins import (  # noqa: E402
    SoftDeleteMixin,
    TimestampedMixin,
    UUIDPrimaryKeyMixin,
)

__all__ = [
    "Base",
    "SoftDeleteMixin",
    "TimestampedMixin",
    "UUIDPrimaryKeyMixin",
    "metadata",
]
