"""Pydantic schemas for the Org HTTP API."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nagara.org.model import AuthProvider


class OrgCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    auth_provider: AuthProvider = AuthProvider.local
    auth_config: dict[str, Any] = Field(default_factory=dict)


class OrgRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    auth_provider: AuthProvider
    auth_config: dict[str, Any]
