from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import redis.asyncio as redis
from fastapi import HTTPException, Request

from app.core.config import settings

logger = logging.getLogger(__name__)

# A small Lua script that performs token-bucket refill and consume atomically.
# KEYS[1] = bucket key
# ARGV[1] = capacity
# ARGV[2] = refill_rate (tokens per second)
# ARGV[3] = now (float seconds)
# ARGV[4] = tokens_to_consume (usually 1)
# Returns: table [allowed(0/1), tokens_left (number), reset_ts (unix seconds)]
LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local consume = tonumber(ARGV[4])

local data = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

-- refill
local elapsed = now - last_refill
if elapsed > 0 then
  local refill = elapsed * refill_rate
  tokens = math.min(capacity, tokens + refill)
  last_refill = now
end

local allowed = 0
if tokens >= consume then
  tokens = tokens - consume
  allowed = 1
end

-- compute reset time: when tokens will be >=1
local reset_ts = 0
if tokens >= 1 then
  reset_ts = now
else
  local needed = 1 - tokens
  reset_ts = now + (needed / refill_rate)
end

-- persist state with an expiry to allow GC of idle keys
redis.call("HMSET", key, "tokens", tostring(tokens), "last_refill", tostring(last_refill))
-- expire slightly longer than time to refill whole bucket (safe default)
local expire_seconds = math.ceil((capacity / refill_rate) * 2)
redis.call("EXPIRE", key, expire_seconds)

return {allowed, tostring(tokens), tostring(reset_ts)}
"""


class RedisTokenBucketRateLimiter:
    """
    Distributed token bucket implemented with Redis and a small atomic Lua script.
    - capacity: max tokens
    - refill_rate: tokens per second
    - prefix: redis key prefix (e.g. "ratelimit:")
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        capacity: int,
        refill_rate: float,
        prefix: str = "rl:",
    ):
        self.redis = redis_client
        self.capacity = int(capacity)
        self.refill_rate = float(refill_rate)
        self.prefix = prefix
        self._script = self.redis.register_script(LUA_TOKEN_BUCKET)

    def _key(self, identifier: str) -> str:
        # Normalise identifier (e.g. user id or IP)
        return f"{self.prefix}{identifier}"

    async def is_allowed(
        self, identifier: str, consume: int = 1
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Returns (allowed: bool, info: dict)
        info contains: limit, remaining, reset (unix int)
        """
        key = self._key(identifier)
        now = time.time()

        # Call Lua script atomically
        try:
            # result: [allowed, tokens_left, reset_ts]
            res = await self._script(
                keys=[key],
                args=[
                    str(self.capacity),
                    str(self.refill_rate),
                    str(now),
                    str(consume),
                ],
            )
        except Exception as e:
            logger.exception(
                "Redis rate limiter lua script failed, falling back to allow=False: %s",
                e,
            )
            # On Redis failure it's often better to fail-open or fail-closed depending on policy.
            # Here we choose fail-open: allow requests when Redis is down. You can change as needed.
            return True, {
                "limit": self.capacity,
                "remaining": self.capacity,
                "reset": int(now + (self.capacity / max(1e-6, self.refill_rate))),
            }

        # Redis returns bytes in some environments; ensure strings
        allowed = bool(int(res[0]))
        tokens_left = float(res[1])
        reset_ts = float(res[2])

        info = {
            "limit": self.capacity,
            "remaining": int(tokens_left) if tokens_left >= 0 else 0,
            "reset": int(reset_ts),
        }
        return allowed, info


def redis_rate_limit(
    capacity: int,
    refill_rate: float,
    prefix: str = "endpoint_rl:",
    get_identifier: Optional[Callable[[Request], str]] = None,
):
    """
    Decorator for endpoint-specific rate limiting using Redis Token Bucket.

    Args:
        capacity: Maximum tokens (requests) in the bucket
        refill_rate: Tokens added per second
        prefix: Redis key prefix for this endpoint
        get_identifier: Optional function to extract identifier from request
                       (defaults to IP address)

    Example:
        @router.post("/login")
        @redis_rate_limit(capacity=5, refill_rate=0.083)  # 5 requests per minute
        async def login(request: Request, ...):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if settings.ENVIRONMENT == "test":
                # Skip rate limiting in test environment
                return await func(*args, **kwargs)
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request and "request" in kwargs:
                request = kwargs["request"]

            if not request:
                raise ValueError(
                    f"Request object not found in endpoint {func.__name__}. "
                    "Make sure your endpoint has a 'request: Request' parameter."
                )

            # Get Redis client from app state
            if not hasattr(request.app.state, "redis"):
                logger.warning(
                    "Redis not available in app.state, allowing request through"
                )
                return await func(*args, **kwargs)

            # Create endpoint-specific rate limiter
            limiter = RedisTokenBucketRateLimiter(
                redis_client=request.app.state.redis,
                capacity=capacity,
                refill_rate=refill_rate,
                prefix=f"{prefix}{func.__name__}:",
            )

            # Get identifier
            if get_identifier:
                identifier = get_identifier(request)
            else:
                # Default: use IP address
                identifier = request.client.host if request.client else "unknown"

            # Check rate limit
            allowed, info = await limiter.is_allowed(identifier)

            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded for this endpoint",
                    headers={
                        "X-RateLimit-Limit": str(info["limit"]),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(info["reset"]),
                        "Retry-After": str(max(0, info["reset"] - int(time.time()))),
                    },
                )

            # Execute endpoint
            response = await func(*args, **kwargs)

            # Add rate limit headers if response supports it
            if hasattr(response, "headers"):
                response.headers["X-RateLimit-Limit"] = str(info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(info["reset"])

            return response

        return wrapper

    return decorator
