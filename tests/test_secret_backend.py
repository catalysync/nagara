"""Secret backend protocol + default env-var implementation."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from nagara.secret_backend import (
    EnvSecretBackend,
    SecretBackend,
    get_secret_backend,
    set_secret_backend,
)


@pytest.mark.asyncio
async def test_env_backend_reads_os_environ():
    b = EnvSecretBackend()
    with patch.dict(os.environ, {"MY_KEY": "hello"}, clear=False):
        assert await b.get("MY_KEY") == "hello"


@pytest.mark.asyncio
async def test_env_backend_returns_none_when_missing():
    b = EnvSecretBackend()
    with patch.dict(os.environ, {}, clear=True):
        assert await b.get("DEFINITELY_UNSET") is None


def test_default_backend_is_env_backend():
    assert isinstance(get_secret_backend(), EnvSecretBackend)


def test_set_secret_backend_swaps_module_singleton():
    class StubBackend(EnvSecretBackend):
        async def get(self, name: str) -> str | None:
            return "stub"

    original = get_secret_backend()
    stub = StubBackend()
    try:
        set_secret_backend(stub)
        assert get_secret_backend() is stub
    finally:
        set_secret_backend(original)


@pytest.mark.asyncio
async def test_custom_backend_subclass_satisfies_protocol():
    """A plain class with the right method is a valid SecretBackend — no ABC
    registration required."""

    class DictBackend:
        def __init__(self, store: dict[str, str]) -> None:
            self._store = store

        async def get(self, name: str) -> str | None:
            return self._store.get(name)

    backend: SecretBackend = DictBackend({"FOO": "bar"})
    assert await backend.get("FOO") == "bar"
    assert await backend.get("missing") is None
