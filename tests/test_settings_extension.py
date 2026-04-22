"""Downstream apps extend :class:`Settings` by subclassing — proven here.

The pattern: core ships ``nagara.config.Settings`` with every knob the
platform itself needs. A downstream app defines::

    class ExtendedSettings(Settings):
        INTEGRATION_API_KEY: SecretStr = SecretStr("")
        VAULT_TOKEN: SecretStr = SecretStr("")
        ...

and instantiates its own singleton. ``Settings.model_config`` inherits so
the ``NAGARA_`` env prefix still applies — the subclass can keep the same
prefix or override ``env_prefix`` for a separate namespace.

These tests walk the pattern end-to-end so a regression in pydantic-settings
inheritance behavior fails here, not in a downstream codebase.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from nagara.config import Environment, Settings


def test_subclass_can_add_fields():
    class ExtendedSettings(Settings):
        INTEGRATION_API_KEY: SecretStr = SecretStr("")
        VAULT_TOKEN: SecretStr = SecretStr("")

    with patch.dict(os.environ, {"NAGARA_INTEGRATION_API_KEY": "sk_test_abc"}, clear=False):
        s = ExtendedSettings()
    assert s.INTEGRATION_API_KEY.get_secret_value() == "sk_test_abc"
    # Core knobs still present — prefix and defaults inherited.
    assert s.APP_NAME == "nagara"


def test_subclass_inherits_helper_methods():
    class ExtendedSettings(Settings):
        EXTRA: str = "x"

    s = ExtendedSettings(ENV=Environment.production, SECRET_KEY=SecretStr("k" * 32))
    assert s.is_production() is True
    assert "EXTRA" in s.safe_dump()


def test_subclass_can_override_env_prefix_for_separate_namespace():
    class ExtendedSettings(Settings):
        INTEGRATION_API_KEY: SecretStr = SecretStr("")

        model_config = SettingsConfigDict(
            env_prefix="downstream_",
            env_file=None,
            extra="ignore",
        )

    with patch.dict(
        os.environ,
        {"DOWNSTREAM_INTEGRATION_API_KEY": "sk_from_downstream_ns"},
        clear=False,
    ):
        s = ExtendedSettings()
    assert s.INTEGRATION_API_KEY.get_secret_value() == "sk_from_downstream_ns"
