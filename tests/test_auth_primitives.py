"""Password hashing + JWT primitive tests — no DB needed."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr

from nagara.auth.hashing import hash_password, verify_password
from nagara.auth.jwt import (
    TokenKind,
    decode_token,
    encode_access_token,
    encode_refresh_token,
)
from nagara.config import Settings

# ── Hashing ────────────────────────────────────────────────────────────────


def test_hash_password_is_not_reversible():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert len(h) > 20
    # Argon2 hashes start with $argon2.
    assert h.startswith("$argon2")


def test_hashing_is_salted_so_repeats_differ():
    assert hash_password("same") != hash_password("same")


def test_verify_password_accepts_correct():
    h = hash_password("s3cret")
    assert verify_password("s3cret", h) is True


def test_verify_password_rejects_wrong():
    h = hash_password("s3cret")
    assert verify_password("wrong", h) is False


def test_verify_password_returns_false_on_garbage_hash():
    # Defensive — stored-hash corruption shouldn't raise on verify.
    assert verify_password("anything", "not-a-real-hash") is False


# ── JWT ────────────────────────────────────────────────────────────────────


def _settings() -> Settings:
    # Unique secret per test so tokens don't cross-validate.
    return Settings(SECRET_KEY=SecretStr("x" * 64))


def test_access_token_roundtrip():
    s = _settings()
    user_id = uuid4()
    tok = encode_access_token(user_id, settings=s)
    decoded = decode_token(tok, settings=s)
    assert decoded["sub"] == str(user_id)
    assert decoded["kind"] == TokenKind.access.value


def test_refresh_token_roundtrip():
    s = _settings()
    user_id = uuid4()
    tok = encode_refresh_token(user_id, settings=s)
    decoded = decode_token(tok, settings=s)
    assert decoded["sub"] == str(user_id)
    assert decoded["kind"] == TokenKind.refresh.value


def test_decode_rejects_token_from_different_secret():
    import jwt as pyjwt

    other = Settings(SECRET_KEY=SecretStr("y" * 64))
    tok = encode_access_token(uuid4(), settings=_settings())
    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_token(tok, settings=other)


def test_decode_rejects_expired_token():
    import jwt as pyjwt

    s = _settings()
    # Negative TTL → issued-and-already-expired.
    tok = encode_access_token(uuid4(), settings=s, ttl=timedelta(seconds=-1))
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(tok, settings=s)


def test_access_and_refresh_are_distinguishable():
    s = _settings()
    user_id = uuid4()
    a = decode_token(encode_access_token(user_id, settings=s), settings=s)
    r = decode_token(encode_refresh_token(user_id, settings=s), settings=s)
    assert a["kind"] != r["kind"]
