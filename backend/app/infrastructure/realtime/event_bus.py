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
