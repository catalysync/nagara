"""User, Group, GroupMember.

Membership of *workspaces* is modelled separately (``Membership``) — these
classes only model "who exists in this Org and which Groups they belong to."
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, TimestampedMixin, UUIDPrimaryKeyMixin
from nagara.db.mixins import utcnow


class User(UUIDPrimaryKeyMixin, TimestampedMixin, Base):
    """A human principal scoped to one Org."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("org_id", "email"),)

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stable IdP subject id — never reuse this for our own keys.
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Argon2id hash from ``nagara.auth.hash_password``. Nullable so users
    # authenticated exclusively via OIDC/SAML don't need a local password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Group(UUIDPrimaryKeyMixin, Base):
    """An SSO or locally-managed group of users within one Org.

    Granting a Workspace role to a Group expands at evaluation time to every
    current member of that Group — the way SSO directories expect to work.
    """

    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("org_id", "name"),)

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("orgs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )


class GroupMember(Base):
    """User-in-Group link. Composite PK (group_id, user_id)."""

    __tablename__ = "group_members"

    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
