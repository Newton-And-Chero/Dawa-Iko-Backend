"""Async Redis client factory."""

from functools import lru_cache
from typing import cast

from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    settings = get_settings()
    return cast(Redis, Redis.from_url(settings.REDIS_URL, decode_responses=True))
