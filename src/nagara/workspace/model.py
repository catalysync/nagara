"""Workspace + Environment.

A Workspace is "the project" — the membership boundary, the asset boundary.
An Environment is a runtime profile within a Workspace (dev/staging/prod or
custom). Connection bindings, secrets, and schedules attach at the Environment
level so the same code can run against different data without code changes.

Invariant: at most one Environment per Workspace can be ``is_default=True``.
Enforced by a partial unique index, not a check constraint, so we get
INSERT/UPDATE atomicity from Postgres.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, TimestampedMixin, UUIDPrimaryKeyMixin


class Workspace(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """The project. Owns assets, holds memberships, contains environments."""

    __tablename__ = "workspaces"
    __table_args__ = (UniqueConstraint("org_id", "slug"),)

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class Environment(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """A runtime profile within a Workspace.

    On Workspace creation we auto-insert one Environment with
    ``slug='default'`` and ``is_default=True``. Users who never need >1 env
    don't see the concept; users who do can create dev/staging/prod alongside.
    """

    __tablename__ = "environments"
    __table_args__ = (
        UniqueConstraint("workspace_id", "slug"),
        # Partial unique index: at most one default per workspace.
        Index(
            "one_default_env_per_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
