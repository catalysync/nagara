"""HTTP routes for Workspaces + Memberships.

Workspace creation auto-creates one ``default`` Environment in the same
transaction, so users who never need >1 env never see the concept.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.db.session import get_session
from nagara.iam.membership import Membership
from nagara.workspace.model import Environment, Workspace
from nagara.workspace.schemas import (
    MembershipCreate,
    MembershipRead,
    WorkspaceCreate,
    WorkspaceRead,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(payload: WorkspaceCreate, session: SessionDep) -> Workspace:
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
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"workspace with slug '{payload.slug}' already exists in this org",
        ) from exc
    await session.refresh(ws)
    return ws


@router.get("", response_model=list[WorkspaceRead])
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
    member = Membership(
        workspace_id=workspace_id,
        user_id=payload.user_id,
        group_id=payload.group_id,
        role=payload.role,
    )
    session.add(member)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="principal is already a member of this workspace",
        ) from exc
    await session.refresh(member)
    return member
