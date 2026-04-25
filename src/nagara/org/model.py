"""Org — the tenant root."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin


class AuthProvider(StrEnum):
    """Which auth protocol an Org uses.

    The enum carries the *protocol*, not a vendor name — specific IdPs
    (Zitadel, Keycloak, WorkOS, Okta, Auth0, …) are configured through
    ``oidc`` or ``saml`` with the provider-specific details living in
    ``Org.auth_config`` (jsonb). Keeps the public surface vendor-neutral so
    new providers don't require core changes.
    """

    local = "local"
    oidc = "oidc"
    saml = "saml"


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
