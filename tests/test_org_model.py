"""Org model schema tests."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.org.model import AuthProvider, Org


def test_org_table_columns_present():
    cols = Org.__table__.columns
    expected = {
        "id",
        "slug",
        "name",
        "auth_provider",
        "auth_config",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert expected.issubset(cols.keys())


def test_org_slug_is_unique():
    insp = inspect(Org)
    slug_col = insp.columns["slug"]
    assert slug_col.unique is True
    assert slug_col.nullable is False


def test_org_auth_provider_enum_is_vendor_neutral():
    # Enum carries the protocol, not the vendor — providers like Zitadel,
    # Keycloak, WorkOS, Okta all configure through 'oidc' or 'saml'.
    assert {p.value for p in AuthProvider} == {"local", "oidc", "saml"}


@pytest.mark.asyncio
async def test_org_can_be_inserted_with_minimal_fields(session: AsyncSession):
    org = Org(slug="acme", name="Acme Inc")
    session.add(org)
    await session.commit()

    assert org.id is not None
    assert org.created_at is not None
    assert org.auth_provider == AuthProvider.local
    assert org.auth_config == {}
    assert org.deleted_at is None


@pytest.mark.asyncio
async def test_org_slug_uniqueness_enforced(session: AsyncSession):
    session.add(Org(slug="dupe", name="One"))
    await session.commit()

    session.add(Org(slug="dupe", name="Two"))
    with pytest.raises(IntegrityError):
        await session.commit()
