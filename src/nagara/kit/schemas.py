from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import UUID4, AfterValidator, BaseModel, ConfigDict, Field


class Schema(BaseModel):
    """Base for every API schema. ``from_attributes=True`` lets endpoints
    return ORM objects directly — Pydantic reads attributes off the model
    instead of requiring a dict."""

    model_config = ConfigDict(from_attributes=True)


class IDSchema(Schema):
    """Adds the canonical ``id: UUID4`` field. ``json_schema_mode_override``
    keeps FastAPI from generating a separate ``-Input`` variant when the
    same schema appears as both a request and response model."""

    id: UUID4 = Field(description="Resource ID.")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_mode_override="serialization",
    )


class TimestampedSchema(Schema):
    created_at: datetime = Field(description="Creation timestamp.")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp.")


def _empty_str_to_none(value: str | None) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return None
        return stripped
    return value


EmptyStrToNone = Annotated[str | None, AfterValidator(_empty_str_to_none)]
"""Use as a field type when the client may send ``""`` for "no value" —
common in HTML forms. Empty strings are coerced to ``None``."""
