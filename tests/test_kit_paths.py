import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from nagara.exceptions import BadRequest, NagaraError
from nagara.kit.paths import (
    ValidatedFileName,
    ValidatedFolderName,
    assert_within,
    safe_join,
)


def test_safe_join_returns_resolved_path_inside_root():
    with tempfile.TemporaryDirectory() as root:
        result = safe_join(root, "subdir", "file.txt")
        assert result.is_relative_to(Path(root).resolve())


def test_safe_join_blocks_dot_dot_traversal():
    with tempfile.TemporaryDirectory() as root, pytest.raises(BadRequest) as exc:
        safe_join(root, "..", "..", "etc", "passwd")
    assert exc.value.error_code == "bad_request"
    assert "etc" in exc.value.extra["path"]


def test_safe_join_blocks_encoded_traversal():
    with tempfile.TemporaryDirectory() as root, pytest.raises(BadRequest):
        safe_join(root, "foo/../../bar")


def test_assert_within_accepts_inside():
    with tempfile.TemporaryDirectory() as root:
        target = Path(root) / "ok.txt"
        target.touch()
        assert_within(root, target)


def test_assert_within_rejects_outside():
    with tempfile.TemporaryDirectory() as root, pytest.raises(BadRequest):
        assert_within(root, "/etc/passwd")


def _build_app() -> TestClient:
    app = FastAPI()

    @app.exception_handler(NagaraError)
    def _h(_, e: NagaraError):
        return JSONResponse(
            status_code=e.status_code,
            content={"error": e.error_code, "extra": e.extra},
        )

    @app.get("/file/{filename}")
    def f(filename: ValidatedFileName):
        return {"name": filename}

    @app.get("/dir/{folder}/{filename}")
    def d(folder: ValidatedFolderName, filename: ValidatedFileName):
        return {"folder": folder, "name": filename}

    return TestClient(app)


def test_validated_filename_accepts_clean_segments():
    c = _build_app()
    assert c.get("/file/report.csv").json() == {"name": "report.csv"}
    assert c.get("/dir/uploads/photo.png").json() == {"folder": "uploads", "name": "photo.png"}


def test_validated_filename_rejects_dot_dot():
    """Exercise the validator directly so the test fails if the dependency
    is removed — going through routes risks 404 short-circuiting."""
    import pytest

    from nagara.exceptions import BadRequest
    from nagara.kit.paths import _validated_filename, _validated_foldername

    for bad in ("..", "../etc", "a/b", "a\\b", ""):
        with pytest.raises(BadRequest):
            _validated_filename(bad)
        with pytest.raises(BadRequest):
            _validated_foldername(bad)
