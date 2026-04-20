"""Tests for layered config loading + deep merge."""

from __future__ import annotations

from nagara.layered import deep_merge, load_pyproject_config, load_toml_config


def test_deep_merge_last_wins_for_scalars():
    assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}


def test_deep_merge_preserves_keys_unique_to_each_layer():
    assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}


def test_deep_merge_recurses_into_nested_dicts():
    result = deep_merge(
        {"db": {"host": "base-host", "port": 5432}},
        {"db": {"host": "override"}},
    )
    assert result == {"db": {"host": "override", "port": 5432}}


def test_deep_merge_is_nondestructive():
    a = {"x": 1}
    b = {"y": 2}
    deep_merge(a, b)
    assert a == {"x": 1}
    assert b == {"y": 2}


def test_deep_merge_list_replaces_not_concatenates():
    """Lists in later layers replace, not extend."""
    result = deep_merge({"items": [1, 2]}, {"items": [3]})
    assert result == {"items": [3]}


def test_load_toml_config_reads_a_plain_toml(tmp_path):
    path = tmp_path / "c.toml"
    path.write_text('app_name = "from-toml"\n')
    assert load_toml_config(path) == {"app_name": "from-toml"}


def test_load_toml_config_returns_empty_for_missing_file(tmp_path):
    missing = tmp_path / "nope.toml"
    assert load_toml_config(missing) == {}


def test_load_pyproject_config_extracts_tool_nagara(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\n\n[tool.nagara]\napp_name = "scoped"\n'
    )
    assert load_pyproject_config(tmp_path / "pyproject.toml") == {"app_name": "scoped"}


def test_load_pyproject_config_returns_empty_when_no_tool_nagara(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    assert load_pyproject_config(tmp_path / "pyproject.toml") == {}


def test_load_pyproject_config_handles_missing_file(tmp_path):
    assert load_pyproject_config(tmp_path / "none.toml") == {}
