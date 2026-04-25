"""FeatureResolver — core's "can this happen?" check, swappable by downstream apps."""

from __future__ import annotations

from uuid import uuid4

import pytest

from nagara.features import (
    FeatureCheck,
    PermissiveResolver,
    get_resolver,
    set_resolver,
)


@pytest.mark.asyncio
async def test_permissive_allows_everything_by_default():
    r = PermissiveResolver()
    org_id = uuid4()
    ws_id = uuid4()

    assert (await r.can_create_workspace(org_id)).allowed is True
    assert (await r.can_invite_member(ws_id)).allowed is True
    assert (await r.can_create_environment(ws_id)).allowed is True


def test_get_resolver_returns_permissive_by_default():
    assert isinstance(get_resolver(), PermissiveResolver)


def test_set_resolver_swaps_the_global():
    from uuid import UUID

    class Deny(PermissiveResolver):
        async def can_create_workspace(self, org_id: UUID) -> FeatureCheck:
            return FeatureCheck(allowed=False, reason="no")

    original = get_resolver()
    deny = Deny()
    try:
        set_resolver(deny)
        assert get_resolver() is deny
    finally:
        set_resolver(original)
