from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from nagara.kit.schemas import EmptyStrToNone, IDSchema, Schema, TimestampedSchema


class _User(IDSchema):
    name: str


def test_id_schema_round_trips():
    u = _User(id=uuid4(), name="alice")
    dumped = u.model_dump()
    assert "id" in dumped
    assert dumped["name"] == "alice"


def test_id_schema_rejects_non_uuid():
    with pytest.raises(ValidationError):
        _User(id="not-a-uuid", name="x")  # ty:ignore[invalid-argument-type]


def test_timestamped_schema_optional_updated_at():
    t = TimestampedSchema(created_at=datetime.now(UTC))
    assert t.updated_at is None
    t2 = TimestampedSchema(created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    assert t2.updated_at is not None


def test_schema_from_attributes_reads_object():
    class Plain:
        def __init__(self, name):
            self.name = name

    class S(Schema):
        name: str

    s = S.model_validate(Plain("zed"))
    assert s.name == "zed"


def test_empty_str_to_none_collapses_blank():
    class F(Schema):
        x: EmptyStrToNone = None

    assert F(x="").x is None
    assert F(x="   ").x is None
    assert F(x=" hi ").x == "hi"
    assert F(x=None).x is None
