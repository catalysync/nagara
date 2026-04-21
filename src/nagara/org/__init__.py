"""Org domain — the tenant root.

An ``Org`` owns workspaces, users, and IdP configuration. Everything in the
system traces back to exactly one Org.
"""

from nagara.org.model import AuthProvider, Org

__all__ = ["AuthProvider", "Org"]
