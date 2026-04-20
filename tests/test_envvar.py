"""Tests for the lazy EnvVar marker."""

from __future__ import annotations

import pytest

from nagara.envvar import EnvVar, resolve


def test_envvar_stores_name():
    v = EnvVar("MY_VAR")
    assert v.name == "MY_VAR"


def test_envvar_is_str_subclass():
    """Subclasses str so it can be placed anywhere a str annotation expects one,
    while still carrying the env var name for later resolution."""
    assert isinstance(EnvVar("X"), str)


def test_envvar_get_value_resolves_from_env(monkeypatch):
    monkeypatch.setenv("MY_VAR", "hello")
    assert EnvVar("MY_VAR").get_value() == "hello"


def test_envvar_get_value_returns_default_if_missing(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    assert EnvVar("NOPE").get_value(default="fallback") == "fallback"


def test_envvar_raises_on_missing_without_default(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    with pytest.raises(KeyError, match="NOPE"):
        EnvVar("NOPE").get_value()


def test_envvar_repr_shows_env_prefix():
    """Repr clearly marks this is a lazy env reference, not a literal string."""
    assert "env:MY_API_KEY" in repr(EnvVar("MY_API_KEY"))


def test_resolve_passes_non_envvars_through(monkeypatch):
    assert resolve("literal") == "literal"
    assert resolve(42) == 42
    assert resolve(None) is None


def test_resolve_materializes_envvar_instances(monkeypatch):
    monkeypatch.setenv("MY_VAR", "resolved")
    assert resolve(EnvVar("MY_VAR")) == "resolved"


def test_resolve_walks_dicts_recursively(monkeypatch):
    monkeypatch.setenv("MY_VAR", "r1")
    monkeypatch.setenv("OTHER", "r2")
    data = {"a": EnvVar("MY_VAR"), "b": "literal", "c": {"nested": EnvVar("OTHER")}}
    assert resolve(data) == {"a": "r1", "b": "literal", "c": {"nested": "r2"}}


def test_resolve_walks_lists(monkeypatch):
    monkeypatch.setenv("X", "x-val")
    assert resolve([EnvVar("X"), "lit"]) == ["x-val", "lit"]
