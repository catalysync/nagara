"""HTTP routes for Workspaces + Memberships.

Workspace creation auto-creates one ``default`` Environment in the same
transaction, so users who never need >1 env never see the concept.

Domain events (``WorkspaceCreated`` / ``MemberAdded``) go through the
durable outbox — staged in the same transaction as the state change. A
separate worker drains the outbox to the in-process EventBus, so no event
is lost if the process crashes between commit and dispatch.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.cli import CLIRouter
from nagara.db.session import get_session
from nagara.events import MemberAdded, WorkspaceCreated
from nagara.features import get_resolver
from nagara.iam.membership import Membership
from nagara.outbox import emit_outboxed
from nagara.workspace.model import Environment, Workspace
from nagara.workspace.schemas import (
    MembershipCreate,
    MembershipRead,
    WorkspaceCreate,
    WorkspaceRead,
)

router = CLIRouter(prefix="/workspaces", tags=["workspaces"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: WorkspaceCreate, session: SessionDep) -> Workspace:
    check = await get_resolver().can_create_workspace(payload.org_id)
    if not check.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=check.reason or "workspace creation not permitted",
        )

    ws = Workspace(**payload.model_dump())
    session.add(ws)
    try:
        await session.flush()  # assign ws.id without committing yet
        session.add(
            Environment(
                workspace_id=ws.id,
                slug="default",
                name="Default",
                is_default=True,
            )
        )
        emit_outboxed(
            session,
            WorkspaceCreated(
                occurred_at=datetime.now(UTC),
                org_id=ws.org_id,
                workspace_id=ws.id,
                slug=ws.slug,
                created_by=ws.created_by,
            ),
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"workspace with slug '{payload.slug}' already exists in this org",
        ) from exc
    await session.refresh(ws)
    return ws


@router.get(
    "",
    response_model=list[WorkspaceRead],
    cli_command="workspace ls",
    cli_summary="List workspaces in an org",
)
async def list_workspaces(
    session: SessionDep,
    org_id: Annotated[UUID, Query(description="Org to scope the listing to")],
) -> list[Workspace]:
    result = await session.execute(
        select(Workspace).where(Workspace.org_id == org_id, Workspace.archived_at.is_(None))
    )
    return list(result.scalars().all())


@router.post(
    "/{workspace_id}/members",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    workspace_id: UUID,
    payload: MembershipCreate,
    session: SessionDep,
) -> Membership:
    check = await get_resolver().can_invite_member(workspace_id)
    if not check.allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=check.reason or "member invitation not permitted",
        )

    member = Membership(
        workspace_id=workspace_id,
        user_id=payload.user_id,
        group_id=payload.group_id,
        role=payload.role,
    )
    session.add(member)
    try:
        await session.flush()  # assign member.id inside the transaction
        emit_outboxed(
            session,
            MemberAdded(
                occurred_at=datetime.now(UTC),
                workspace_id=workspace_id,
                membership_id=member.id,
                user_id=member.user_id,
                group_id=member.group_id,
                # StrEnum stringifies to its .value; bare str passes through.
                role=str(member.role),
            ),
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="principal is already a member of this workspace",
        ) from exc
    await session.refresh(member)
    return member
