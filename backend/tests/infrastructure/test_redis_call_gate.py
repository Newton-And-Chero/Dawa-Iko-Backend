from app.core.config import Settings
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.call_e.redis_call_gate import CALL_ENGINE_ENABLED_KEY, RedisCallGate


async def test_absent_key_falls_back_to_the_configured_default() -> None:
    await get_redis().delete(CALL_ENGINE_ENABLED_KEY)

    off = RedisCallGate(get_redis(), Settings(CALLS_ENABLED_DEFAULT=False))
    assert await off.is_enabled() is False
    assert (await off.status()).default_enabled is False

    on = RedisCallGate(get_redis(), Settings(CALLS_ENABLED_DEFAULT=True))
    assert await on.is_enabled() is True


async def test_disable_then_enable_overrides_the_default() -> None:
    gate = RedisCallGate(get_redis(), Settings(CALLS_ENABLED_DEFAULT=True))

    state = await gate.disable()
    assert state.enabled is False
    assert await gate.is_enabled() is False

    state = await gate.enable()
    assert state.enabled is True
    assert state.expires_at is None
    assert await gate.is_enabled() is True


async def test_enable_with_ttl_reports_an_expiry_and_lapses() -> None:
    gate = RedisCallGate(get_redis(), Settings(CALLS_ENABLED_DEFAULT=False))

    state = await gate.enable(ttl_seconds=120)
    assert state.enabled is True
    assert state.expires_at is not None

    await get_redis().delete(CALL_ENGINE_ENABLED_KEY)
    assert await gate.is_enabled() is False
