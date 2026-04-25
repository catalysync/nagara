from __future__ import annotations

from pathlib import Path

from nagara.exceptions import BadRequest


def safe_join(root: str | Path, *parts: str) -> Path:
    """Join ``parts`` against ``root`` and raise :class:`BadRequest` if the
    result escapes ``root``. Use any time a request supplies a path
    fragment that's appended to a server-controlled directory."""
    base = Path(root).resolve()
    candidate = (base.joinpath(*parts)).resolve()
    if base != candidate and base not in candidate.parents:
        raise BadRequest("path traversal detected", extra={"path": "/".join(parts)})
    return candidate


def assert_within(root: str | Path, candidate: str | Path) -> Path:
    """Resolve ``candidate`` and assert it sits inside ``root``."""
    base = Path(root).resolve()
    target = Path(candidate).resolve()
    if base != target and base not in target.parents:
        raise BadRequest("path outside allowed root", extra={"path": str(candidate)})
    return target
