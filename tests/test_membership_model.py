"""Membership model tests."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.iam.membership import Membership, Role
from nagara.iam.model import Group, User
from nagara.org.model import Org
from nagara.workspace.model import Workspace


async def _scaffold(session: AsyncSession) -> tuple[Org, Workspace, User, Group]:
    org = Org(slug="acme", name="Acme")
    session.add(org)
    await session.commit()
    user = User(org_id=org.id, email="alice@example.com")
    group = Group(org_id=org.id, name="engineers")
    ws = Workspace(org_id=org.id, slug="proj", name="Proj")
    session.add_all([user, group, ws])
    await session.commit()
    return org, ws, user, group


def test_role_enum_choices():
    assert {r.value for r in Role} == {"owner", "admin", "editor", "viewer", "guest"}


def test_membership_columns_present():
    cols = Membership.__table__.columns
    expected = {
        "id",
        "workspace_id",
        "user_id",
        "group_id",
        "role",
        "added_by",
        "added_at",
    }
    assert expected.issubset(cols.keys())


@pytest.mark.asyncio
async def test_membership_with_user(session: AsyncSession):
    _, ws, user, _ = await _scaffold(session)
    m = Membership(workspace_id=ws.id, user_id=user.id, role=Role.editor)
    session.add(m)
    await session.commit()
    assert m.id is not None


@pytest.mark.asyncio
async def test_membership_with_group(session: AsyncSession):
    _, ws, _, group = await _scaffold(session)
    m = Membership(workspace_id=ws.id, group_id=group.id, role=Role.viewer)
    session.add(m)
    await session.commit()
    assert m.id is not None


@pytest.mark.asyncio
async def test_membership_user_xor_group_constraint(session: AsyncSession):
    _, ws, user, group = await _scaffold(session)
    # Both set: must fail.
    m = Membership(workspace_id=ws.id, user_id=user.id, group_id=group.id, role=Role.editor)
    session.add(m)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_membership_neither_user_nor_group_constraint(session: AsyncSession):
    _, ws, _, _ = await _scaffold(session)
    m = Membership(workspace_id=ws.id, role=Role.editor)
    session.add(m)
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_user_unique_per_workspace(session: AsyncSession):
    _, ws, user, _ = await _scaffold(session)
    session.add(Membership(workspace_id=ws.id, user_id=user.id, role=Role.editor))
    await session.commit()
    session.add(Membership(workspace_id=ws.id, user_id=user.id, role=Role.viewer))
    with pytest.raises(IntegrityError):
        await session.commit()
