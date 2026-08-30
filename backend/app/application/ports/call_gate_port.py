from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class CallEngineState:
    enabled: bool
    expires_at: datetime | None
    default_enabled: bool


class CallGatePort(Protocol):
    async def is_enabled(self) -> bool: ...

    async def status(self) -> CallEngineState: ...

    async def enable(self, ttl_seconds: int | None = None) -> CallEngineState: ...

    async def disable(self) -> CallEngineState: ...
