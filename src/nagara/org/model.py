"""Org — the tenant root."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class AuthProvider(StrEnum):
    """How an Org authenticates its users.

    ``local``  — username/password handled by the app itself.
    ``zitadel`` — self-hosted or hosted Zitadel cluster (OIDC/OAuth).
    ``workos`` — WorkOS-managed SSO (SAML, OIDC, magic link).
    """

    local = "local"
    zitadel = "zitadel"
    workos = "workos"


class Org(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
    """A tenant. The top of every ownership chain in the system."""

    __tablename__ = "orgs"

    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_provider: Mapped[AuthProvider] = mapped_column(
        String(32),
        nullable=False,
        default=AuthProvider.local,
    )
    auth_config: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    billing_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="trial",
    )
