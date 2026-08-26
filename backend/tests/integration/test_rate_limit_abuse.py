"""Adversarial suite for the Redis-backed rate limit on `POST /sweeps/query`
(Sprint 09) — the one endpoint that spends real money and rings real phones
per request, so it must not be abusable. Hammers the endpoint past the
limit, confirms the window resets, and confirms the limiter's own Redis
keys don't accumulate unboundedly (a TTL on every key)."""

import asyncio

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.enums import CommodityCategory, FacilitySource, FacilityType
from app.infrastructure.cache.redis import get_redis
from app.infrastructure.db.repositories.commodity_repository import SqlAlchemyCommodityRepository
from app.infrastructure.db.repositories.facility_repository import SqlAlchemyFacilityRepository
from app.main import app

_RATE_LIMIT_KEY_PATTERN = "rate_limit:sweeps_query:*"


async def _seed_commodity_and_facility(db_session: AsyncSession) -> None:
    await SqlAlchemyCommodityRepository(db_session).add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    await SqlAlchemyFacilityRepository(db_session).add(
        Facility(
            name="Rate Limit Test Dispensary",
            type=FacilityType.DISPENSARY,
            county="Kirinyaga",
            sub_county="Mwea",
            ward="Wamumu",
            gps_lat=-0.6849,
            gps_lng=37.3667,
            phone_number="+254700000070",
            source=FacilitySource.KMHFL,
        )
    )


def _strict_settings(*, limit: int, window_seconds: int) -> Settings:
    return Settings(
        CALL_E_MODE="mock",
        FACILITY_IMPORT_MODE="mock",
        SMS_MODE="mock",
        PUBLIC_QUERY_RATE_LIMIT=limit,
        PUBLIC_QUERY_RATE_WINDOW_SECONDS=window_seconds,
    )


async def _clear_rate_limit_keys() -> None:
    redis = get_redis()
    keys = [k async for k in redis.scan_iter(_RATE_LIMIT_KEY_PATTERN)]
    if keys:
        await redis.delete(*keys)


async def test_burst_past_the_limit_gets_429_then_the_window_resets(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_commodity_and_facility(db_session)
    app.dependency_overrides[get_settings] = lambda: _strict_settings(
        limit=2, window_seconds=1
    )
    body = {"commodity": "Carbetocin", "geography": {"kind": "county", "county": "Kirinyaga"}}

    await _clear_rate_limit_keys()
    try:
        first = await client.post("/v1/sweeps/query", json=body)
        second = await client.post("/v1/sweeps/query", json=body)
        third = await client.post("/v1/sweeps/query", json=body)

        assert first.status_code == 202
        assert second.status_code == 202
        assert third.status_code == 429
        assert "Retry-After" in third.headers

        await asyncio.sleep(1.1)

        after_reset = await client.post("/v1/sweeps/query", json=body)
        assert after_reset.status_code == 202
    finally:
        await _clear_rate_limit_keys()
        app.dependency_overrides.pop(get_settings, None)


async def test_hammering_the_endpoint_never_lets_more_than_the_limit_through(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_commodity_and_facility(db_session)
    limit = 5
    app.dependency_overrides[get_settings] = lambda: _strict_settings(
        limit=limit, window_seconds=30
    )
    body = {"commodity": "Carbetocin", "geography": {"kind": "county", "county": "Kirinyaga"}}

    await _clear_rate_limit_keys()
    try:
        responses = await asyncio.gather(
            *(client.post("/v1/sweeps/query", json=body) for _ in range(25))
        )
        statuses = [r.status_code for r in responses]
        assert statuses.count(202) == limit
        assert statuses.count(429) == 25 - limit
        assert all(status in (202, 429) for status in statuses)
    finally:
        await _clear_rate_limit_keys()
        app.dependency_overrides.pop(get_settings, None)


async def test_rate_limit_keys_carry_a_ttl_and_do_not_accumulate_unbounded(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """A key with no expiry would grow forever, one per distinct client IP —
    an unbounded-memory footgun in Redis. Every key this limiter writes must
    carry a TTL no larger than the configured window."""
    await _seed_commodity_and_facility(db_session)
    window_seconds = 30
    app.dependency_overrides[get_settings] = lambda: _strict_settings(
        limit=100, window_seconds=window_seconds
    )
    body = {"commodity": "Carbetocin", "geography": {"kind": "county", "county": "Kirinyaga"}}

    await _clear_rate_limit_keys()
    try:
        response = await client.post("/v1/sweeps/query", json=body)
        assert response.status_code == 202

        redis = get_redis()
        keys = [k async for k in redis.scan_iter(_RATE_LIMIT_KEY_PATTERN)]
        assert len(keys) == 1
        ttl = await redis.ttl(keys[0])
        assert 0 < ttl <= window_seconds
    finally:
        await _clear_rate_limit_keys()
        app.dependency_overrides.pop(get_settings, None)
