import asyncio
import contextlib
from collections import defaultdict
from functools import lru_cache

from fastapi import WebSocket

from app.application.ports.realtime_event_bus_port import RealtimeEventBusPort
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.realtime.event_bus import RealtimeEventBus


class ConnectionManager:
    def __init__(self, event_bus: RealtimeEventBusPort) -> None:
        self._event_bus = event_bus
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._relay_tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[channel].add(websocket)
            if channel not in self._relay_tasks:
                self._relay_tasks[channel] = asyncio.create_task(self._relay(channel))

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(channel)
            if sockets is None or websocket not in sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                del self._connections[channel]
                task = self._relay_tasks.pop(channel, None)
                if task is not None:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    def subscriber_count(self, channel: str) -> int:
        return len(self._connections.get(channel, ()))

    async def _relay(self, channel: str) -> None:
        async for event in self._event_bus.subscribe(channel):
            for websocket in list(self._connections.get(channel, ())):
                with contextlib.suppress(Exception):
                    await websocket.send_json(event)


@lru_cache
def get_connection_manager() -> ConnectionManager:
    return ConnectionManager(RealtimeEventBus(get_redis()))
