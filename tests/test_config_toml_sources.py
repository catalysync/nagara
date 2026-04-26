"""TOML + profile sources merged into ``Settings``.

Priority order (highest wins), proved by these tests:

    1. init kwargs              (explicit to the Settings(...) call)
    2. env vars + .env file     (standard pydantic-settings sources)
    3. active profile           (``~/.config/nagara/profiles.toml`` section)
    4. user config TOML         (``~/.config/nagara/config.toml``)
    5. pyproject.toml           (``[tool.nagara]`` table)
    6. Settings field defaults
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import patch

from nagara.config import Settings


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))


def test_pyproject_values_pick_up(tmp_path: Path, hermetic_env):
    _write(
        tmp_path / "pyproject.toml",
        """
        [tool.nagara]
        APP_NAME = "from-pyproject"
        POSTGRES_HOST = "pg.pyproject"
        """,
    )
    with patch.dict(os.environ, {"NAGARA_PYPROJECT": str(tmp_path / "pyproject.toml")}):
        s = Settings()
    assert s.APP_NAME == "from-pyproject"
    assert s.POSTGRES_HOST == "pg.pyproject"


def test_user_toml_overrides_pyproject(tmp_path: Path, hermetic_env):
    _write(
        tmp_path / "pyproject.toml",
        """
        [tool.nagara]
        APP_NAME = "from-pyproject"
        POSTGRES_HOST = "pg.pyproject"
        """,
    )
    _write(
        tmp_path / "config.toml",
        """
        POSTGRES_HOST = "pg.user"
        """,
    )
    with patch.dict(
        os.environ,
        {
            "NAGARA_PYPROJECT": str(tmp_path / "pyproject.toml"),
            "NAGARA_USER_CONFIG": str(tmp_path / "config.toml"),
        },
    ):
        s = Settings()
    assert s.APP_NAME == "from-pyproject"  # pyproject still wins for unset keys
    assert s.POSTGRES_HOST == "pg.user"


def test_active_profile_overrides_user_toml(tmp_path: Path, hermetic_env):
    _write(
        tmp_path / "config.toml",
        """
        POSTGRES_HOST = "pg.user"
        LOG_LEVEL = "INFO"
        """,
    )
    _write(
        tmp_path / "profiles.toml",
        """
        active = "dev"

        [profiles.dev]
        POSTGRES_HOST = "pg.profile"
        LOG_LEVEL = "DEBUG"
        """,
    )
    with patch.dict(
        os.environ,
        {
            "NAGARA_USER_CONFIG": str(tmp_path / "config.toml"),
            "NAGARA_PROFILES": str(tmp_path / "profiles.toml"),
        },
    ):
        s = Settings()
    assert s.POSTGRES_HOST == "pg.profile"
    assert s.LOG_LEVEL == "DEBUG"


def test_nagara_profile_env_selects_profile(tmp_path: Path, hermetic_env):
    _write(
        tmp_path / "profiles.toml",
        """
        active = "dev"

        [profiles.dev]
        LOG_LEVEL = "DEBUG"

        [profiles.prod]
        LOG_LEVEL = "ERROR"
        """,
    )
    with patch.dict(
        os.environ,
        {
            "NAGARA_PROFILES": str(tmp_path / "profiles.toml"),
            "NAGARA_PROFILE": "prod",
        },
    ):
        s = Settings()
    assert s.LOG_LEVEL == "ERROR"


def test_env_var_overrides_profile(tmp_path: Path, hermetic_env):
    _write(
        tmp_path / "profiles.toml",
        """
        active = "dev"

        [profiles.dev]
        POSTGRES_HOST = "pg.profile"
        """,
    )
    with patch.dict(
        os.environ,
        {
            "NAGARA_PROFILES": str(tmp_path / "profiles.toml"),
            "NAGARA_POSTGRES_HOST": "pg.env",
        },
    ):
        s = Settings()
    assert s.POSTGRES_HOST == "pg.env"


def test_init_kwargs_win_over_everything(tmp_path: Path, hermetic_env):
    _write(
        tmp_path / "pyproject.toml",
        """
        [tool.nagara]
        POSTGRES_HOST = "pg.pyproject"
        """,
    )
    with patch.dict(
        os.environ,
        {
            "NAGARA_PYPROJECT": str(tmp_path / "pyproject.toml"),
            "NAGARA_POSTGRES_HOST": "pg.env",
        },
    ):
        s = Settings(POSTGRES_HOST="pg.init")
    assert s.POSTGRES_HOST == "pg.init"


def test_missing_files_fall_back_to_defaults(hermetic_env):
    # No files, no env — everything comes from field defaults.
    with patch.dict(
        os.environ,
        {
            "NAGARA_PYPROJECT": "/nonexistent/pyproject.toml",
            "NAGARA_USER_CONFIG": "/nonexistent/config.toml",
            "NAGARA_PROFILES": "/nonexistent/profiles.toml",
        },
    ):
        s = Settings()
    assert s.APP_NAME == "nagara"  # default
    assert s.POSTGRES_HOST == "127.0.0.1"


def test_toml_keys_are_case_insensitive_like_env(tmp_path: Path, hermetic_env):
    # pydantic-settings with case_sensitive=False treats env vars case-insensitively;
    # TOML keys get the same treatment so "postgres_host" or "POSTGRES_HOST" both work.
    _write(
        tmp_path / "config.toml",
        """
        postgres_host = "pg.lower"
        """,
    )
    with patch.dict(os.environ, {"NAGARA_USER_CONFIG": str(tmp_path / "config.toml")}):
        s = Settings()
    assert s.POSTGRES_HOST == "pg.lower"
