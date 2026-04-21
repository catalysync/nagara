"""Password hashing via argon2id (pwdlib default).

Argon2id is the current OWASP recommendation — memory-hard, resistant to
GPU/ASIC attacks. Parameters are pwdlib's defaults, which track the
`draft-irtf-cfrg-argon2` suggested values.

Never store passwords anywhere but the hash — no logging, no events, no
audit fields. The scrubber in :mod:`nagara.secrets` is a safety net, not
permission to be careless.
"""

from __future__ import annotations

from pwdlib import PasswordHash

# Built once per process — creating the hasher is measurable overhead.
_hasher = PasswordHash.recommended()


def hash_password(plaintext: str) -> str:
    """Return an argon2id-encoded hash. Safe to store."""
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Check the plaintext against a stored hash. Returns ``False`` on any
    error — callers can treat a garbled stored hash as "wrong password"
    rather than an exception."""
    try:
        return _hasher.verify(plaintext, hashed)
    except Exception:
        return False
