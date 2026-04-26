from datetime import UTC, datetime
from uuid import UUID

from nagara.kit.utils import generate_uuid, utc_now


def test_utc_now_is_tz_aware_utc():
    now = utc_now()
    assert isinstance(now, datetime)
    assert now.tzinfo is UTC


def test_utc_now_advances():
    a = utc_now()
    b = utc_now()
    assert b >= a


def test_generate_uuid_returns_uuid4():
    u = generate_uuid()
    assert isinstance(u, UUID)
    assert u.version == 4


def test_generate_uuid_unique():
    assert generate_uuid() != generate_uuid()
