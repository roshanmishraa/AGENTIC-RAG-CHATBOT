from __future__ import annotations
import time
import redis.asyncio as redis
from fastapi import Request, HTTPException, status

from app.settings import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


async def check_rate_limit(identifier: str, limit: int = None, window_seconds: int = 60):
    """
    Sliding-window rate limiter using Redis sorted sets.
    identifier = user_id (if authenticated) or IP address (if not).
    """
    limit = limit or settings.RATE_LIMIT_PER_MINUTE
    key = f"ratelimit:{identifier}"
    now = time.time()
    window_start = now - window_seconds

    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)   # drop requests outside the window
    pipe.zadd(key, {str(now): now})               # record this request
    pipe.zcard(key)                                # count requests in current window
    pipe.expire(key, window_seconds)
    results = await pipe.execute()

    request_count = results[2]

    if request_count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {limit} requests per {window_seconds}s. Try again shortly.",
        )


async def rate_limit_dependency(request: Request):
    """FastAPI dependency — add `Depends(rate_limit_dependency)` to any route."""
    # Prefer authenticated user_id (set by rbac.py earlier in the dependency chain),
    # fall back to client IP for unauthenticated endpoints (e.g. login, signup).
    identifier = getattr(request.state, "user_id", None) or request.client.host
    await check_rate_limit(identifier)