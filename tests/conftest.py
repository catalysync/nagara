"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

from nagara.config import Settings


@pytest.fixture
def hermetic_env(monkeypatch: pytest.MonkeyPatch):
    """Scrub any NAGARA_* env var and silence the on-disk ``.env`` file so a
    stray local config (developer machine, CI quirk) can't bleed into a
    test that's asserting field defaults or layered TOML behavior."""
    for key in list(os.environ):
        if key.startswith("NAGARA_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", "/nonexistent/.env")
