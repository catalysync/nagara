"""Workspace membership.

A Membership grants exactly one Role to exactly one principal — User or Group,
never both — for one Workspace.

The principal-XOR-shape is enforced by a check constraint on the table so that
even raw SQL inserts can't violate it.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, UUIDPrimaryKeyMixin
from nagara.db.mixins import utcnow


class Role(StrEnum):
    """Workspace-scoped roles. Order is *not* hierarchy — authz happens via
    explicit role-permission tables, not by ranking."""

    owner = "owner"
    admin = "admin"
    editor = "editor"
    viewer = "viewer"
    guest = "guest"


class Membership(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        # Exactly one of user_id / group_id must be set.
        CheckConstraint(
            "(user_id IS NOT NULL) <> (group_id IS NOT NULL)",
            name="principal_user_xor_group",
        ),
        UniqueConstraint("workspace_id", "user_id"),
        UniqueConstraint("workspace_id", "group_id"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    group_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=True,
    )
    role: Mapped[Role] = mapped_column(String(32), nullable=False)
    added_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
