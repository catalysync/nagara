"""Type aliases for arbitrary JSON shapes.

Use when modeling a payload whose structure isn't known at static-type
time — webhook bodies, third-party API responses, freeform metadata
columns. Reach for a Pydantic model first; only use these when you
genuinely don't have a schema."""

from __future__ import annotations

from typing import Any

JSONDict = dict[str, Any]
JSONList = list[Any]
JSONObject = JSONDict | JSONList
JSONAny = JSONObject | None
