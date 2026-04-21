"""Cloud extends core's :class:`Settings` by subclassing it — proven here.

The pattern: core ships ``nagara.config.Settings`` with every knob the
platform itself needs. The private cloud repo defines::

    class CloudSettings(Settings):
        STRIPE_SECRET_KEY: SecretStr = SecretStr("")
        INFISICAL_TOKEN: SecretStr = SecretStr("")
        ...

and instantiates its own singleton. ``Settings.model_config`` inherits so
the ``NAGARA_`` env prefix still applies — cloud-specific env vars can use
the same prefix or the subclass can override ``env_prefix``.

Tests walk this path end-to-end so a regression in pydantic-settings
inheritance behavior breaks our tests, not cloud.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from nagara.config import Environment, Settings


def test_cloud_can_subclass_settings_and_add_fields():
    class CloudSettings(Settings):
        STRIPE_SECRET_KEY: SecretStr = SecretStr("")
        INFISICAL_TOKEN: SecretStr = SecretStr("")

    with patch.dict(os.environ, {"NAGARA_STRIPE_SECRET_KEY": "sk_test_abc"}, clear=False):
        s = CloudSettings()
    assert s.STRIPE_SECRET_KEY.get_secret_value() == "sk_test_abc"
    # Core knobs still present — prefix and defaults inherited.
    assert s.APP_NAME == "nagara"


def test_subclass_inherits_helper_methods():
    class CloudSettings(Settings):
        EXTRA: str = "x"

    s = CloudSettings(ENV=Environment.production, SECRET_KEY=SecretStr("k" * 32))
    assert s.is_production() is True
    assert "EXTRA" in s.safe_dump()


def test_subclass_can_override_env_prefix_for_separate_namespace():
    class CloudSettings(Settings):
        STRIPE_SECRET_KEY: SecretStr = SecretStr("")

        model_config = SettingsConfigDict(
            env_prefix="nagara_cloud_",
            env_file=None,
            extra="ignore",
        )

    with patch.dict(
        os.environ,
        {"NAGARA_CLOUD_STRIPE_SECRET_KEY": "sk_from_cloud_ns"},
        clear=False,
    ):
        s = CloudSettings()
    assert s.STRIPE_SECRET_KEY.get_secret_value() == "sk_from_cloud_ns"
