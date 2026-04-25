"""HTTP routes for Orgs.

This is the bedrock-tenant-creation endpoint. Auth is intentionally absent in
v0 — the next PR will add an admin-only guard once the auth layer lands.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.db.session import get_session
from nagara.org.model import Org
from nagara.org.schemas import OrgCreate, OrgRead

router = APIRouter(prefix="/orgs", tags=["orgs"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=OrgRead, status_code=status.HTTP_201_CREATED)
async def create_org(payload: OrgCreate, session: SessionDep) -> Org:
    org = Org(**payload.model_dump())
    session.add(org)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"org with slug '{payload.slug}' already exists",
        ) from exc
    await session.refresh(org)
    return org
