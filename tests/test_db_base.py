"""Base + mixins shape tests — no live database required."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from nagara.db import Base, SoftDeleteMixin, TimestampedMixin, UUIDPrimaryKeyMixin


def test_base_has_naming_convention():
    nc = Base.metadata.naming_convention
    assert nc["pk"] == "%(table_name)s_pkey"
    assert nc["fk"] == "%(table_name)s_%(column_0_N_name)s_fkey"
    assert nc["uq"] == "%(table_name)s_%(column_0_N_name)s_key"


def test_uuid_primary_key_mixin_emits_uuid_column():
    class SampleUuidPk(UUIDPrimaryKeyMixin, Base):
        __tablename__ = "_sample_uuid_pk"

    pk = SampleUuidPk.__table__.columns["id"]
    assert pk.primary_key is True
    assert isinstance(pk.default.arg(None), UUID)


def test_timestamped_mixin_adds_created_and_updated():
    class SampleTimestamped(TimestampedMixin, Base):
        __tablename__ = "_sample_ts"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)

    cols = SampleTimestamped.__table__.columns
    assert "created_at" in cols
    assert "updated_at" in cols
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False
    # server-side default present so the DB stamps the row even if the app forgets
    assert cols["created_at"].server_default is not None


def test_soft_delete_mixin_adds_deleted_at_nullable():
    class SampleSoftDelete(SoftDeleteMixin, Base):
        __tablename__ = "_sample_soft"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)

    cols = SampleSoftDelete.__table__.columns
    assert "deleted_at" in cols
    assert cols["deleted_at"].nullable is True


def test_combined_mixins_produce_all_columns():
    class SampleFull(UUIDPrimaryKeyMixin, TimestampedMixin, SoftDeleteMixin, Base):
        __tablename__ = "_sample_full"

    cols = SampleFull.__table__.columns
    assert {"id", "created_at", "updated_at", "deleted_at"}.issubset(cols.keys())


def test_timestamped_default_factory_returns_datetime():
    class SampleDefaultFactory(TimestampedMixin, Base):
        __tablename__ = "_sample_default_factory"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)

    factory = SampleDefaultFactory.__table__.columns["created_at"].default.arg
    value = factory(None)
    assert isinstance(value, datetime)
    assert value.tzinfo is not None
