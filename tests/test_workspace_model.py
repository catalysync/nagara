"""Workspace + Environment model tests."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.iam.model import User
from nagara.org.model import Org
from nagara.workspace.model import Environment, Workspace


async def _make_org_user(session: AsyncSession) -> tuple[Org, User]:
    org = Org(slug="acme", name="Acme")
    session.add(org)
    await session.commit()
    user = User(org_id=org.id, email="alice@example.com")
    session.add(user)
    await session.commit()
    return org, user


def test_workspace_columns_present():
    cols = Workspace.__table__.columns
    expected = {
        "id",
        "org_id",
        "slug",
        "name",
        "description",
        "created_by",
        "created_at",
        "archived_at",
    }
    assert expected.issubset(cols.keys())


def test_environment_columns_present():
    cols = Environment.__table__.columns
    expected = {
        "id",
        "workspace_id",
        "slug",
        "name",
        "is_default",
        "description",
        "created_at",
        "archived_at",
    }
    assert expected.issubset(cols.keys())


def test_environment_has_partial_unique_index_for_default():
    indexes = getattr(Environment.__table__, "indexes", set())
    matches = [ix for ix in indexes if "default" in (ix.name or "") and ix.unique]
    assert matches, "expected a partial unique index enforcing one default env per workspace"
    assert {c.name for c in matches[0].columns} == {"workspace_id"}


@pytest.mark.asyncio
async def test_workspace_slug_unique_per_org(session: AsyncSession):
    org, user = await _make_org_user(session)
    session.add(Workspace(org_id=org.id, slug="proj", name="Proj", created_by=user.id))
    await session.commit()
    session.add(Workspace(org_id=org.id, slug="proj", name="Other", created_by=user.id))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_environment_slug_unique_per_workspace(session: AsyncSession):
    org, user = await _make_org_user(session)
    ws = Workspace(org_id=org.id, slug="proj", name="Proj", created_by=user.id)
    session.add(ws)
    await session.commit()

    session.add(Environment(workspace_id=ws.id, slug="dev", name="Dev"))
    await session.commit()
    session.add(Environment(workspace_id=ws.id, slug="dev", name="Dev2"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_environment_default_defaults_to_false(session: AsyncSession):
    org, user = await _make_org_user(session)
    ws = Workspace(org_id=org.id, slug="proj", name="Proj", created_by=user.id)
    session.add(ws)
    await session.commit()

    env = Environment(workspace_id=ws.id, slug="dev", name="Dev")
    session.add(env)
    await session.commit()
    assert env.is_default is False
