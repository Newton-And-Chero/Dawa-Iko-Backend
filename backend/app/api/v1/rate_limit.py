from fastapi import Depends, HTTPException, Request

from app.core.config import Settings, get_settings
from app.infrastructure.cache.redis import get_redis


async def rate_limit_public_query(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    redis = get_redis()
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:sweeps_query:{client_ip}"

    current = await redis.incr(key)
    if current == 1:
        await redis.expire(key, settings.PUBLIC_QUERY_RATE_WINDOW_SECONDS)

    if current > settings.PUBLIC_QUERY_RATE_LIMIT:
        ttl = await redis.ttl(key)
        retry_after = ttl if ttl > 0 else settings.PUBLIC_QUERY_RATE_WINDOW_SECONDS
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded — try again later",
            headers={"Retry-After": str(retry_after)},
        )
