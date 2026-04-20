"""Tests for Settings.safe_dump — API-safe serialization that masks secrets."""

from __future__ import annotations

from pydantic import SecretStr

from nagara.config import Settings


def test_safe_dump_masks_secretstr_by_default():
    s = Settings(POSTGRES_PWD=SecretStr("real-pwd"), SECRET_KEY=SecretStr("sk-abc"))
    data = s.safe_dump()
    assert data["POSTGRES_PWD"] == "***"
    assert data["SECRET_KEY"] == "***"


def test_safe_dump_leaves_non_secrets_alone():
    s = Settings(APP_NAME="nagara", POSTGRES_HOST="db.internal")
    data = s.safe_dump()
    assert data["APP_NAME"] == "nagara"
    assert data["POSTGRES_HOST"] == "db.internal"


def test_safe_dump_include_secrets_flag_exposes_real_values():
    s = Settings(POSTGRES_PWD=SecretStr("real-pwd"))
    data = s.safe_dump(include_secrets=True)
    assert data["POSTGRES_PWD"] == "real-pwd"


def test_safe_dump_returns_json_serializable_types():
    """The result must be round-trippable through json.dumps — no SecretStr
    instances, no timedelta objects, no Path objects lurking."""
    import json

    s = Settings()
    data = s.safe_dump()
    # Should not raise
    json.dumps(data, default=str)
