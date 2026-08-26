"""Redis pub/sub-backed RealtimeEventBus (Sprint 06).

Why Redis pub/sub and not an in-process broadcaster: the webhook that
produces an event may be handled by any Celery worker or any API process
(once this runs with more than one uvicorn worker), while the WS client is
connected to one specific API process. Redis pub/sub is the one piece of
shared infrastructure every process already has (Sprint 00), so it's the
fan-out point — publish once per channel, every subscribed process delivers
to its own connected clients.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis


class RealtimeEventBus:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, channel: str, event: dict[str, Any]) -> None:
        await self._redis.publish(channel, json.dumps(event))

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                yield json.loads(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
