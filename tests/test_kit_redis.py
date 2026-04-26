import pytest

from nagara.kit.redis import create_redis


def _redis_available() -> bool:
    import asyncio

    try:

        async def _ping():
            r = create_redis()
            try:
                await r.ping()
                return True
            finally:
                await r.aclose()

        return asyncio.run(_ping())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _redis_available(),
    reason="redis not reachable at REDIS_URL — skipping integration tests",
)


async def test_create_redis_returns_async_client():
    r = create_redis()
    pong = await r.ping()
    assert pong is True
    await r.aclose()


async def test_client_name_tagged_with_env_and_process():
    r = create_redis("worker")
    info = await r.client_info()
    assert info["name"].startswith("nagara.")
    assert info["name"].endswith(".worker")
    await r.aclose()


async def test_create_redis_default_process_name_is_app():
    r = create_redis()
    info = await r.client_info()
    assert info["name"].endswith(".app")
    await r.aclose()


async def test_decode_responses_returns_str_not_bytes():
    r = create_redis()
    key = "_nagara_test_decode_check"
    await r.set(key, "hello")
    val = await r.get(key)
    assert val == "hello"
    assert isinstance(val, str)
    await r.delete(key)
    await r.aclose()
