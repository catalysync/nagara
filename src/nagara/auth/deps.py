"""FastAPI dependencies for authenticated endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.auth.jwt import TokenKind, decode_token
from nagara.config import get_current_settings
from nagara.db.session import get_session
from nagara.iam.model import User

# ``auto_error=False`` so we return 401 with our own body instead of FastAPI's
# default "Not authenticated" shape.
_bearer = HTTPBearer(auto_error=False)


async def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """Resolve the caller to a :class:`User`.

    Raises 401 if the bearer token is missing, malformed, expired, signed
    with the wrong secret, or belongs to a user that's been deactivated.
    Refresh tokens are rejected here — they're only valid against
    ``POST /auth/refresh``.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(creds.credentials, settings=get_current_settings())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("kind") != TokenKind.access.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="refresh token cannot authorize this request",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw = payload.get("sub")
    try:
        user_id = UUID(raw) if isinstance(raw, str) else None
    except (ValueError, TypeError):
        user_id = None
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="malformed token")

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user does not exist or is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]
