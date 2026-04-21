"""FeatureResolver — core asks "can this happen?", cloud answers.

Core endpoints call into a :class:`FeatureResolver` before acting on a
request. OSS self-hosters get the :class:`PermissiveResolver` (everything
allowed). The private cloud repo registers its own implementation at
startup that checks subscription state, plan quotas, and rate limits.

Adding a new check:
  1. Add an ``async def can_X(self, ...) -> FeatureCheck`` method here,
     with a permissive default implementation.
  2. Call it at the relevant endpoint: if ``not check.allowed`` → 403.
  3. Cloud overrides the method in its subclass.

No coordination between repos needed — cloud's subclass gets the new
permissive default for free.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class FeatureCheck:
    """Result of a gate. ``reason`` is shown to the caller on denial."""

    allowed: bool
    reason: str | None = None


class FeatureResolver:
    """Default base + permissive implementation. Subclass in cloud and
    override whichever checks need subscription/quota logic."""

    async def can_create_workspace(self, org_id: UUID) -> FeatureCheck:  # noqa: ARG002
        return FeatureCheck(allowed=True)

    async def can_invite_member(self, workspace_id: UUID) -> FeatureCheck:  # noqa: ARG002
        return FeatureCheck(allowed=True)

    async def can_create_environment(self, workspace_id: UUID) -> FeatureCheck:  # noqa: ARG002
        return FeatureCheck(allowed=True)


# Alias kept for semantic clarity at call sites in OSS / tests.
PermissiveResolver = FeatureResolver


_resolver: FeatureResolver = PermissiveResolver()


def get_resolver() -> FeatureResolver:
    """Return the currently-registered resolver."""
    return _resolver


def set_resolver(resolver: FeatureResolver) -> None:
    """Replace the process-wide resolver. Cloud calls this at app startup."""
    global _resolver
    _resolver = resolver
