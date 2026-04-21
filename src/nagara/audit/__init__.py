"""Audit domain — append-only log of authn/authz decisions and data access."""

from nagara.audit.model import AuditDecision, AuditEvent

__all__ = ["AuditDecision", "AuditEvent"]
