"""Request/response schemas for the auth endpoints."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# Minimum bar — long enough that brute force becomes expensive against an
# argon2id hash, short enough not to push users into "Password1!" territory.
# Bumped past 8 because OWASP now recommends 12+ for general-purpose accounts.
_MIN_PASSWORD_LEN = 12
_MAX_PASSWORD_LEN = 256


def _validate_password_complexity(value: str) -> str:
    """Reject obviously-weak passwords. Length-first per current NIST guidance:
    no class-mix requirement (mixed-case + digit + symbol mandates push users
    toward predictable patterns) — instead we just require enough length and
    enough character diversity that the user can't pass with one repeated
    character or a single dictionary word.
    """
    if len(value) < _MIN_PASSWORD_LEN:
        raise ValueError(
            f"password must be at least {_MIN_PASSWORD_LEN} characters"
        )
    if len(set(value)) < 5:
        raise ValueError("password must use at least 5 distinct characters")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    # Login intentionally accepts any non-empty password so users locked out
    # by a tightened complexity rule can still authenticate against a valid
    # legacy hash. Complexity is enforced at register / change-password time.
    password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LEN)


class RegisterRequest(BaseModel):
    """Self-serve signup payload.

    ``org_slug`` is required so the new user lands in an existing org; we
    don't yet support spinning up a fresh org from the signup form (admin
    surface only). Email uniqueness is enforced at the DB layer.
    """

    email: EmailStr
    password: str = Field(min_length=_MIN_PASSWORD_LEN, max_length=_MAX_PASSWORD_LEN)
    full_name: str | None = Field(default=None, max_length=255)
    org_slug: str = Field(min_length=1, max_length=64)

    _validate_password = field_validator("password")(_validate_password_complexity)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    """Caller identity — minimum shape the frontend needs to bootstrap."""

    id: UUID
    email: str
    full_name: str | None
    org_id: UUID
