"""Local auth — email + password, JWT issuance, request dependency.

What's here is OSS-grade: enough to sign users in, protect endpoints, and
rotate refresh tokens. What's *not* here and lives in cloud or a follow-up:

- OIDC / SAML flows (the ``auth_provider`` enum already carries the marker)
- Password reset + email verification (needs transactional email, cloud)
- MFA, WebAuthn (scope creep for v0)
- Server-side refresh token revocation (access tokens are short-lived so
  compromise blast radius is bounded; add a denylist table when we need
  admin "force logout")
"""

from nagara.auth.deps import CurrentUser, current_user
from nagara.auth.hashing import hash_password, verify_password
from nagara.auth.jwt import (
    TokenKind,
    decode_token,
    encode_access_token,
    encode_refresh_token,
)

__all__ = [
    "CurrentUser",
    "TokenKind",
    "current_user",
    "decode_token",
    "encode_access_token",
    "encode_refresh_token",
    "hash_password",
    "verify_password",
]
