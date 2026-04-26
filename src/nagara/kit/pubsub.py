"""In-process async pub/sub keyed by an arbitrary topic id."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

_SENTINEL: Any = object()
logger = logging.getLogger(__name__)


class PubSub[K]:
    def __init__(self, maxsize: int = 0) -> None:
        # ``maxsize=0`` keeps the legacy unbounded behaviour. Pass a positive
        # int to cap each subscriber's buffer; a slow consumer then drops new
        # events instead of pinning memory.
        self._maxsize = maxsize
        self._queues: dict[K, list[asyncio.Queue[Any]]] = {}

    def subscribe(self, topic: K) -> AsyncIterator[Any]:
        # Reserve one extra slot so close()'s sentinel always fits, even when
        # the user-visible buffer is full.
        capacity = self._maxsize + 1 if self._maxsize else 0
        queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=capacity)
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
            # When bounded, the visible capacity is maxsize and the +1 slot
            # is reserved for the sentinel — refuse new events at qsize==maxsize.
            if self._maxsize and queue.qsize() >= self._maxsize:
                logger.warning("pubsub queue full on topic=%r; dropping event", topic)
                continue
            await queue.put(event)

    def close(self, topic: K) -> None:
        for queue in self._queues.pop(topic, []):
            queue.put_nowait(_SENTINEL)
