"""Port for the real-time event bus (Sprint 06): fan-out of state-change
events to whichever API process holds the subscribed WS/SSE connection.
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol


class RealtimeEventBusPort(Protocol):
    async def publish(self, channel: str, event: dict[str, Any]) -> None: ...

    def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]: ...
