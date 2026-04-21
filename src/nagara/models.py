"""Aggregator that imports every model module.

Importing this module guarantees every table is registered on
``nagara.db.Base.metadata``. Alembic's ``env.py`` imports this so
``--autogenerate`` sees the full schema; tests use it to populate
``Base.metadata.create_all``.

Add a new domain here whenever you create one — that single import is the
only registration step needed.
"""

from __future__ import annotations

from nagara import outbox as _outbox  # noqa: F401
from nagara.audit import model as _audit_model  # noqa: F401
from nagara.iam import membership as _iam_membership  # noqa: F401
from nagara.iam import model as _iam_model  # noqa: F401
from nagara.iam import token as _iam_token  # noqa: F401
from nagara.org import model as _org_model  # noqa: F401
from nagara.workspace import model as _workspace_model  # noqa: F401
