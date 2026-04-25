"""APIToken + AuditEvent model tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.audit.model import AuditDecision, AuditEvent
from nagara.iam.model import User
from nagara.iam.token import APIToken
from nagara.org.model import Org
from nagara.workspace.model import Workspace


async def _scaffold(session: AsyncSession) -> tuple[Org, Workspace, User]:
    org = Org(slug="acme", name="Acme")
    session.add(org)
    await session.commit()
    user = User(org_id=org.id, email="alice@example.com")
    ws = Workspace(org_id=org.id, slug="proj", name="Proj")
    session.add_all([user, ws])
    await session.commit()
    return org, ws, user


# ── APIToken ───────────────────────────────────────────────────────────────


def test_api_token_columns_present():
    cols = APIToken.__table__.columns
    expected = {
        "id",
        "org_id",
        "workspace_id",
        "user_id",
        "name",
        "token_hash",
        "prefix",
        "scopes",
        "last_used_at",
        "expires_at",
        "created_at",
        "revoked_at",
    }
    assert expected.issubset(cols.keys())


@pytest.mark.asyncio
async def test_api_token_user_pat(session: AsyncSession):
    org, _, user = await _scaffold(session)
    tok = APIToken(
        org_id=org.id,
        user_id=user.id,
        name="my pat",
        token_hash="x" * 64,
        prefix="ng_pat_abcd",
    )
    session.add(tok)
    await session.commit()
    assert tok.id is not None
    assert tok.scopes == []
    assert tok.workspace_id is None


@pytest.mark.asyncio
async def test_api_token_service_principal(session: AsyncSession):
    org, ws, _ = await _scaffold(session)
    tok = APIToken(
        org_id=org.id,
        workspace_id=ws.id,
        name="ci",
        token_hash="y" * 64,
        prefix="ng_svc_xyz",
        scopes=["read:assets", "write:assets"],
    )
    session.add(tok)
    await session.commit()
    assert tok.user_id is None
    assert tok.scopes == ["read:assets", "write:assets"]


# ── AuditEvent ─────────────────────────────────────────────────────────────


def test_audit_event_columns_present():
    cols = AuditEvent.__table__.columns
    expected = {
        "id",
        "org_id",
        "workspace_id",
        "actor_user_id",
        "actor_token_id",
        "action",
        "resource_kind",
        "resource_id",
        "decision",
        "reason",
        "ip_address",
        "user_agent",
        "request_id",
        "occurred_at",
    }
    assert expected.issubset(cols.keys())


def test_audit_decision_enum():
    assert {d.value for d in AuditDecision} == {"allow", "deny"}


@pytest.mark.asyncio
async def test_audit_event_insert_minimal(session: AsyncSession):
    org, ws, user = await _scaffold(session)
    event = AuditEvent(
        org_id=org.id,
        workspace_id=ws.id,
        actor_user_id=user.id,
        action="workspace.create",
        decision=AuditDecision.allow,
        request_id=uuid4(),
    )
    session.add(event)
    await session.commit()
    assert event.id is not None
    assert event.occurred_at is not None
