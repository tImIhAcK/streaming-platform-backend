from __future__ import annotations

import logging
import time
from typing import Any, Dict, Tuple

import redis.asyncio as redis

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
