from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis

from app.application.ports.call_gate_port import CallEngineState
from app.core.config import Settings

CALL_ENGINE_ENABLED_KEY = "call_engine:enabled"

_DISABLED_MARKER = "0"
_ENABLED_MARKER = "on"


class RedisCallGate:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self._redis = redis
        self._default_enabled = settings.CALLS_ENABLED_DEFAULT

    async def is_enabled(self) -> bool:
        raw = await self._redis.get(CALL_ENGINE_ENABLED_KEY)
        if raw is None:
            return self._default_enabled
        return bool(raw != _DISABLED_MARKER)

    async def status(self) -> CallEngineState:
        raw = await self._redis.get(CALL_ENGINE_ENABLED_KEY)
        if raw is None:
            return CallEngineState(
                enabled=self._default_enabled,
                expires_at=None,
                default_enabled=self._default_enabled,
            )
        if raw == _DISABLED_MARKER:
            return CallEngineState(
                enabled=False, expires_at=None, default_enabled=self._default_enabled
            )
        ttl = await self._redis.ttl(CALL_ENGINE_ENABLED_KEY)
        expires_at = (
            datetime.now(UTC) + timedelta(seconds=ttl) if isinstance(ttl, int) and ttl > 0 else None
        )
        return CallEngineState(
            enabled=True, expires_at=expires_at, default_enabled=self._default_enabled
        )

    async def enable(self, ttl_seconds: int | None = None) -> CallEngineState:
        if ttl_seconds is not None and ttl_seconds > 0:
            await self._redis.set(CALL_ENGINE_ENABLED_KEY, _ENABLED_MARKER, ex=ttl_seconds)
        else:
            await self._redis.set(CALL_ENGINE_ENABLED_KEY, _ENABLED_MARKER)
        return await self.status()

    async def disable(self) -> CallEngineState:
        await self._redis.set(CALL_ENGINE_ENABLED_KEY, _DISABLED_MARKER)
        return await self.status()
