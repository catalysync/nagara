"""Auth endpoint tests — login, refresh, CurrentUser dependency."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from nagara.auth.api import router as auth_router
from nagara.auth.deps import CurrentUser
from nagara.auth.hashing import hash_password
from nagara.auth.jwt import encode_access_token, encode_refresh_token
from nagara.config import Settings, temporary_settings
from nagara.db.session import get_session
from nagara.iam.model import User
from nagara.org.model import Org


async def _seed_user(session: AsyncSession, password: str = "s3cret") -> User:
    org = Org(slug="acme", name="Acme")
    session.add(org)
    await session.commit()
    user = User(
        org_id=org.id,
        email="alice@example.com",
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.commit()
    return user


@pytest.fixture
def fixed_secret_settings():
    """Pin a secret key for deterministic token generation inside tests."""
    with temporary_settings(SECRET_KEY=SecretStr("x" * 64)) as s:
        yield s


# ── Login ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_returns_access_and_refresh(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    await _seed_user(session)
    res = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "s3cret"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert isinstance(body["refresh_token"], str) and body["refresh_token"]


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    await _seed_user(session)
    res = await client.post("/auth/login", json={"email": "alice@example.com", "password": "nope"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_hides_whether_user_exists(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    missing = await client.post("/auth/login", json={"email": "ghost@example.com", "password": "x"})
    await _seed_user(session)
    wrong = await client.post("/auth/login", json={"email": "alice@example.com", "password": "x"})
    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["detail"] == wrong.json()["detail"]


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    user = await _seed_user(session)
    user.is_active = False
    await session.commit()
    res = await client.post(
        "/auth/login", json={"email": "alice@example.com", "password": "s3cret"}
    )
    assert res.status_code == 401


# ── Refresh ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_exchanges_for_new_pair(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    user = await _seed_user(session)
    rt = encode_refresh_token(user.id, settings=fixed_secret_settings)
    res = await client.post("/auth/refresh", json={"refresh_token": rt})
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"] and body["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    user = await _seed_user(session)
    at = encode_access_token(user.id, settings=fixed_secret_settings)
    res = await client.post("/auth/refresh", json={"refresh_token": at})
    assert res.status_code == 401
    assert "not a refresh token" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_refresh_rejects_garbage(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    res = await client.post("/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert res.status_code == 401


# ── CurrentUser dep ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_current_user_dep_resolves_valid_access_token(
    api_client_with_protected: tuple[AsyncClient, FastAPI],
    session: AsyncSession,
    fixed_secret_settings: Settings,
):
    client, _ = api_client_with_protected
    user = await _seed_user(session)
    at = encode_access_token(user.id, settings=fixed_secret_settings)
    res = await client.get("/whoami", headers={"Authorization": f"Bearer {at}"})
    assert res.status_code == 200
    assert res.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_current_user_dep_rejects_missing_header(
    api_client_with_protected: tuple[AsyncClient, FastAPI], fixed_secret_settings: Settings
):
    client, _ = api_client_with_protected
    res = await client.get("/whoami")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_current_user_dep_rejects_refresh_token(
    api_client_with_protected: tuple[AsyncClient, FastAPI],
    session: AsyncSession,
    fixed_secret_settings: Settings,
):
    client, _ = api_client_with_protected
    user = await _seed_user(session)
    rt = encode_refresh_token(user.id, settings=fixed_secret_settings)
    res = await client.get("/whoami", headers={"Authorization": f"Bearer {rt}"})
    assert res.status_code == 401


# ── Fixtures ───────────────────────────────────────────────────────────────


# ── /auth/me ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_returns_caller_identity(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession, fixed_secret_settings: Settings
):
    client, _ = api_client
    user = await _seed_user(session)
    at = encode_access_token(user.id, settings=fixed_secret_settings)
    res = await client.get("/auth/me", headers={"Authorization": f"Bearer {at}"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == "alice@example.com"
    assert body["id"] == str(user.id)
    assert body["org_id"] == str(user.org_id)


@pytest.mark.asyncio
async def test_me_rejects_unauthenticated(api_client: tuple[AsyncClient, FastAPI]):
    client, _ = api_client
    res = await client.get("/auth/me")
    assert res.status_code == 401


# ── /auth/register ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_identity(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession
):
    client, _ = api_client
    org = Org(slug="acme", name="Acme")
    session.add(org)
    await session.commit()
    res = await client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "password": "correct horse battery",
            "full_name": "Bob",
            "org_slug": "acme",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "bob@example.com"
    assert body["full_name"] == "Bob"
    assert body["org_id"] == str(org.id)


@pytest.mark.asyncio
async def test_register_rejects_short_password(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession
):
    client, _ = api_client
    session.add(Org(slug="acme", name="Acme"))
    await session.commit()
    res = await client.post(
        "/auth/register",
        json={
            "email": "x@example.com",
            "password": "short",
            "org_slug": "acme",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_low_complexity_password(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession
):
    client, _ = api_client
    session.add(Org(slug="acme", name="Acme"))
    await session.commit()
    # 12 chars but only 1 distinct character — fails the diversity check.
    res = await client.post(
        "/auth/register",
        json={"email": "x@example.com", "password": "aaaaaaaaaaaa", "org_slug": "acme"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_missing_org(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession
):
    client, _ = api_client
    res = await client.post(
        "/auth/register",
        json={
            "email": "x@example.com",
            "password": "correct horse battery",
            "org_slug": "ghost-org",
        },
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(
    api_client: tuple[AsyncClient, FastAPI], session: AsyncSession
):
    client, _ = api_client
    await _seed_user(session)
    res = await client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "password": "correct horse battery",
            "org_slug": "acme",
        },
    )
    assert res.status_code == 409


@pytest_asyncio.fixture
async def api_client(session: AsyncSession):
    app = FastAPI()
    app.include_router(auth_router)

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app


@pytest_asyncio.fixture
async def api_client_with_protected(session: AsyncSession):
    app = FastAPI()

    @app.get("/whoami")
    async def whoami(user: CurrentUser) -> dict[str, str]:
        return {"email": user.email, "id": str(user.id)}

    async def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, app
