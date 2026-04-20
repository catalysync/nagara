"""Tests for the profiles system."""

from __future__ import annotations

import pytest

from nagara.profiles import (
    Profile,
    ProfileStore,
    active_profile_name,
    load_profiles,
    save_profiles,
)


def test_profile_is_just_a_named_dict_of_overrides():
    p = Profile(name="dev", overrides={"ENV": "development"})
    assert p.name == "dev"
    assert p.overrides == {"ENV": "development"}


def test_profilestore_can_add_and_get():
    store = ProfileStore()
    store.upsert(Profile(name="dev", overrides={"ENV": "development"}))
    store.upsert(Profile(name="prod", overrides={"ENV": "production"}))
    assert store.get("dev").overrides == {"ENV": "development"}
    assert store.get("prod").overrides == {"ENV": "production"}


def test_profilestore_lists_names():
    store = ProfileStore()
    store.upsert(Profile(name="a", overrides={}))
    store.upsert(Profile(name="b", overrides={}))
    assert set(store.names()) == {"a", "b"}


def test_profilestore_active_starts_none():
    assert ProfileStore().active is None


def test_profilestore_activate_sets_active():
    store = ProfileStore()
    store.upsert(Profile(name="staging", overrides={}))
    store.activate("staging")
    assert store.active == "staging"


def test_profilestore_activate_raises_for_unknown():
    with pytest.raises(KeyError, match="ghost"):
        ProfileStore().activate("ghost")


def test_profilestore_remove():
    store = ProfileStore()
    store.upsert(Profile(name="temp", overrides={}))
    store.remove("temp")
    assert "temp" not in store.names()


def test_profilestore_remove_clears_active_if_active(tmp_path):
    store = ProfileStore()
    store.upsert(Profile(name="x", overrides={}))
    store.activate("x")
    store.remove("x")
    assert store.active is None


def test_save_and_load_profiles_roundtrip(tmp_path):
    path = tmp_path / "profiles.toml"
    store = ProfileStore()
    store.upsert(Profile(name="dev", overrides={"ENV": "development", "LOG_LEVEL": "DEBUG"}))
    store.upsert(Profile(name="prod", overrides={"ENV": "production"}))
    store.activate("dev")
    save_profiles(store, path)

    loaded = load_profiles(path)
    assert set(loaded.names()) == {"dev", "prod"}
    assert loaded.active == "dev"
    assert loaded.get("dev").overrides == {"ENV": "development", "LOG_LEVEL": "DEBUG"}


def test_load_profiles_returns_empty_store_for_missing_file(tmp_path):
    store = load_profiles(tmp_path / "none.toml")
    assert list(store.names()) == []
    assert store.active is None


def test_active_profile_name_reads_from_env_override(monkeypatch):
    """The NAGARA_PROFILE env var overrides whatever's saved on disk."""
    monkeypatch.setenv("NAGARA_PROFILE", "staging")
    assert active_profile_name(default="dev") == "staging"


def test_active_profile_name_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("NAGARA_PROFILE", raising=False)
    assert active_profile_name(default="dev") == "dev"
