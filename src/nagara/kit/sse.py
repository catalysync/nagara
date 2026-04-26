from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any


def format_event(data: Any, *, event: str | None = None, id: str | None = None) -> str:
    parts: list[str] = []
    if id is not None:
        parts.append(f"id: {id}")
    if event is not None:
        parts.append(f"event: {event}")
    payload = data if isinstance(data, str) else json.dumps(data, default=str)
    for line in payload.splitlines() or [""]:
        parts.append(f"data: {line}")
    parts.append("")
    parts.append("")
    return "\n".join(parts)


def progress_event(data: Any, *, id: str | None = None) -> str:
    return format_event(data, event="progress", id=id)


def complete_event(data: Any = None, *, id: str | None = None) -> str:
    return format_event(
        data if data is not None else {"status": "complete"}, event="complete", id=id
    )


def error_event(message: str, *, id: str | None = None, **extra: Any) -> str:
    return format_event({"error": message, **extra}, event="error", id=id)


async def stream_events(events: AsyncIterator[Any]) -> AsyncIterator[bytes]:
    async for ev in events:
        if isinstance(ev, str):
            yield ev.encode("utf-8")
        else:
            yield format_event(ev).encode("utf-8")
