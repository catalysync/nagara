"""Pydantic schemas for the Workspace + Membership HTTP API."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nagara.iam.membership import Role


class WorkspaceCreate(BaseModel):
    org_id: UUID
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    created_by: UUID | None = None


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    slug: str
    name: str
    description: str | None
    created_by: UUID | None


class MembershipCreate(BaseModel):
    user_id: UUID | None = None
    group_id: UUID | None = None
    role: Role

    @model_validator(mode="after")
    def _exactly_one_principal(self) -> Self:
        if (self.user_id is None) == (self.group_id is None):
            raise ValueError("provide exactly one of user_id or group_id")
        return self


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    user_id: UUID | None
    group_id: UUID | None
    role: Role
