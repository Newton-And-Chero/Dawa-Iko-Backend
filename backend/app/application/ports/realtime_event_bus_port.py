from collections.abc import AsyncIterator
from typing import Any, Protocol


class RealtimeEventBusPort(Protocol):
    async def publish(self, channel: str, event: dict[str, Any]) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]: ...
