from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Path as PathParam

from nagara.exceptions import BadRequest

_BAD_SEGMENT_CHARS = re.compile(r"[/\\]|\.\.|\x00")


def _reject_bad_segment(value: str, kind: str) -> str:
    # Defenses, in order: empty, dir-traversal / path-separator / NUL,
    # leading dot (hidden file or `..`-prefix smuggle), leading `~`
    # (home expansion in some downstream tools), and OS-absolute paths.
    if (
        not value
        or _BAD_SEGMENT_CHARS.search(value)
        or value.startswith((".", "~"))
        or Path(value).is_absolute()
    ):
        raise BadRequest(f"invalid {kind}", extra={kind: value})
    return value


def _validated_filename(filename: str = PathParam(...)) -> str:
    return _reject_bad_segment(filename, "filename")


def _validated_foldername(folder: str = PathParam(...)) -> str:
    return _reject_bad_segment(folder, "folder")


ValidatedFileName = Annotated[str, Depends(_validated_filename)]
ValidatedFolderName = Annotated[str, Depends(_validated_foldername)]


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
