"""Workspace domain — collaboration unit, asset owner, environment owner.

A Workspace belongs to an Org and contains 1..N Environments. Auto-creating a
``default`` Environment on Workspace creation lets users ignore the env concept
until they need >1.
"""

from nagara.workspace.model import Environment, Workspace

__all__ = ["Environment", "Workspace"]
