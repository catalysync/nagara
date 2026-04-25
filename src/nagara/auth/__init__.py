"""Local auth — email + password, JWT issuance, request dependency.

Enough to sign users in, protect endpoints, and rotate refresh tokens.
Deferred to follow-up work:

- OIDC / SAML flows (the ``auth_provider`` enum already carries the marker)
- Password reset + email verification (requires transactional email)
- MFA, WebAuthn
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
