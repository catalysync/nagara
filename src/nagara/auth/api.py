"""Auth endpoints: /auth/login, /auth/refresh.

``/auth/logout`` is intentionally absent for v0 — access tokens are short
lived (15 min default) and refresh tokens are stateless, so "logout" is a
client-side concern (drop the tokens). Server-side revocation needs a
denylist table; add when admin "force logout" becomes a real requirement.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.auth.deps import CurrentUser
from nagara.auth.hashing import hash_password, verify_password
from nagara.auth.jwt import (
    TokenKind,
    decode_token,
    encode_access_token,
    encode_refresh_token,
)
from nagara.auth.schemas import (
    LoginRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from nagara.config import get_current_settings
from nagara.db.session import get_session
from nagara.iam.model import User
from nagara.org.model import Org

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    """Return the caller's identity.

    Needed so the browser can resolve ``org_id`` from a bearer token — the
    JWT intentionally carries only ``sub`` so rotating org assignments don't
    invalidate already-issued tokens.
    """
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        org_id=user.org_id,
    )


@router.post(
    "/register",
    response_model=MeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, session: SessionDep) -> MeResponse:
    """Self-serve signup.

    Creates an inactive-by-default? No — we activate immediately so the
    follow-up login works without an admin step. Email verification will
    gate this once it's wired; until then, treat ``/auth/register`` as a
    closed-beta surface (ingress should rate-limit + invite-gate).

    Returns the same shape as ``/auth/me`` so the frontend can pivot to
    the bootstrap state without an extra round-trip.
    """
    org = (
        await session.execute(select(Org).where(Org.slug == payload.org_slug))
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="org not found",
        )

    existing = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        # Generic conflict — don't confirm whether the email is taken vs
        # whether the org is wrong, to limit user-enumeration.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email is already registered",
        )

    user = User(
        org_id=org.id,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        org_id=user.org_id,
    )


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginRequest, session: SessionDep) -> TokenPair:
    """Email + password → access + refresh token pair.

    Always returns the same error message / status for missing users and
    bad passwords so the endpoint can't be used as a user-enumeration
    oracle.
    """
    settings = get_current_settings()
    user = (
        await session.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()

    generic = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="invalid email or password",
    )
    if user is None or not user.is_active or not user.password_hash:
        raise generic
    if not verify_password(payload.password, user.password_hash):
        raise generic

    return TokenPair(
        access_token=encode_access_token(user.id, settings=settings),
        refresh_token=encode_refresh_token(user.id, settings=settings),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenPair:
    """Exchange a refresh token for a new access+refresh pair. Rejects
    access tokens (kind check) and inactive users."""
    settings = get_current_settings()
    try:
        decoded = decode_token(payload.refresh_token, settings=settings)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired refresh token",
        ) from exc

    if decoded.get("kind") != TokenKind.refresh.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not a refresh token",
        )

    raw = decoded.get("sub")
    try:
        user_id = UUID(raw) if isinstance(raw, str) else None
    except (ValueError, TypeError):
        user_id = None
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="malformed refresh token",
        )
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user does not exist or is inactive",
        )

    return TokenPair(
        access_token=encode_access_token(user.id, settings=settings),
        refresh_token=encode_refresh_token(user.id, settings=settings),
    )
