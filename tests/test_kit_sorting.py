from enum import StrEnum

import pytest

from nagara.exceptions import ValidationFailed
from nagara.kit.sorting import parse_sorting


class _Sort(StrEnum):
    name = "name"
    created = "created"


def test_default_used_when_raw_missing():
    out = parse_sorting(None, _Sort, default=["-created"])
    assert out == [(_Sort.created, True)]


def test_empty_string_uses_default():
    out = parse_sorting("", _Sort, default=["name"])
    assert out == [(_Sort.name, False)]


def test_empty_list_uses_default():
    out = parse_sorting([], _Sort, default=["name"])
    assert out == [(_Sort.name, False)]


def test_no_default_returns_empty_list():
    out = parse_sorting(None, _Sort)
    assert out == []


def test_csv_string_parsed_into_pairs():
    out = parse_sorting("name,-created", _Sort)
    assert out == [(_Sort.name, False), (_Sort.created, True)]


def test_sequence_of_strings_parsed():
    out = parse_sorting(["name", "-created"], _Sort)
    assert out == [(_Sort.name, False), (_Sort.created, True)]


def test_unknown_field_raises_validation_failed():
    with pytest.raises(ValidationFailed) as exc:
        parse_sorting("bogus", _Sort)
    assert exc.value.error_code == "validation_failed"
    assert exc.value.errors[0].loc == ("query", "sort")
    assert "bogus" in exc.value.errors[0].input  # ty:ignore[unsupported-operator]


def test_partial_invalid_collects_all_errors():
    with pytest.raises(ValidationFailed) as exc:
        parse_sorting("name,-bogus,bad", _Sort)
    msgs = [e.input for e in exc.value.errors]
    assert "-bogus" in msgs
    assert "bad" in msgs
    assert "name" not in msgs


def test_whitespace_in_csv_stripped():
    out = parse_sorting(" name , -created ", _Sort)
    assert out == [(_Sort.name, False), (_Sort.created, True)]
