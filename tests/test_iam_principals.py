"""User, Group, GroupMember model tests."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.iam.model import Group, GroupMember, User
from nagara.org.model import Org


async def _make_org(session: AsyncSession, slug: str = "acme") -> Org:
    org = Org(slug=slug, name=slug.title())
    session.add(org)
    await session.commit()
    return org


def test_user_table_columns_present():
    cols = User.__table__.columns
    expected = {
        "id",
        "org_id",
        "email",
        "full_name",
        "external_id",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert expected.issubset(cols.keys())


def test_group_table_columns_present():
    cols = Group.__table__.columns
    assert {"id", "org_id", "name", "external_id", "created_at"}.issubset(cols.keys())


def test_group_member_composite_pk():
    pk_cols = {c.name for c in GroupMember.__table__.primary_key}
    assert pk_cols == {"group_id", "user_id"}


@pytest.mark.asyncio
async def test_user_insert_with_minimal_fields(session: AsyncSession):
    org = await _make_org(session)
    user = User(org_id=org.id, email="alice@example.com")
    session.add(user)
    await session.commit()

    assert user.id is not None
    assert user.is_active is True
    assert user.full_name is None
    assert user.external_id is None


@pytest.mark.asyncio
async def test_user_email_unique_per_org(session: AsyncSession):
    org = await _make_org(session)
    session.add(User(org_id=org.id, email="dupe@example.com"))
    await session.commit()
    session.add(User(org_id=org.id, email="dupe@example.com"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_same_email_allowed_across_orgs(session: AsyncSession):
    a = await _make_org(session, "a")
    b = await _make_org(session, "b")
    session.add_all(
        [
            User(org_id=a.id, email="shared@example.com"),
            User(org_id=b.id, email="shared@example.com"),
        ]
    )
    await session.commit()  # should not raise


@pytest.mark.asyncio
async def test_group_name_unique_per_org(session: AsyncSession):
    org = await _make_org(session)
    session.add(Group(org_id=org.id, name="engineers"))
    await session.commit()
    session.add(Group(org_id=org.id, name="engineers"))
    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.asyncio
async def test_group_member_link(session: AsyncSession):
    org = await _make_org(session)
    user = User(org_id=org.id, email="u@example.com")
    group = Group(org_id=org.id, name="g")
    session.add_all([user, group])
    await session.commit()

    session.add(GroupMember(group_id=group.id, user_id=user.id))
    await session.commit()
