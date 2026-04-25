from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import redis.asyncio as _async_redis
from redis import ConnectionError, RedisError, TimeoutError
from redis.asyncio.retry import Retry
from redis.backoff import default_backoff

from nagara.config import settings

if TYPE_CHECKING:
    Redis = _async_redis.Redis[str]
else:
    Redis = _async_redis.Redis


_RETRY_ON_ERROR: list[type[RedisError]] = [ConnectionError, TimeoutError]
_RETRY = Retry(default_backoff(), retries=50)


type ProcessName = Literal["app", "rate_limit", "worker", "script"]


def create_redis(process: ProcessName = "app") -> Redis:
    return _async_redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        retry_on_error=_RETRY_ON_ERROR,
        retry=_RETRY,
        client_name=f"nagara.{settings.ENV.value}.{process}",
    )
