"""In-process async pub/sub keyed by an arbitrary topic id."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

_SENTINEL: Any = object()


class PubSub[K]:
    def __init__(self) -> None:
        self._queues: dict[K, list[asyncio.Queue[Any]]] = {}

    def subscribe(self, topic: K) -> AsyncIterator[Any]:
        # Caller must iterate the returned async generator to consume
        # buffered events. Dropping it without iterating leaves the queue
        # registered until close(topic). For long-lived topics with stuck
        # subscribers, set a max queue size and drop on full.
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._queues.setdefault(topic, []).append(queue)

        async def _iter() -> AsyncIterator[Any]:
            try:
                while True:
                    item = await queue.get()
                    if item is _SENTINEL:
                        return
                    yield item
            finally:
                if queue in self._queues.get(topic, []):
                    self._queues[topic].remove(queue)

        return _iter()

    async def publish(self, topic: K, event: Any) -> None:
        for queue in self._queues.get(topic, []):
            await queue.put(event)

    def close(self, topic: K) -> None:
        for queue in self._queues.pop(topic, []):
            queue.put_nowait(_SENTINEL)
