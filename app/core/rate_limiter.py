"""
Rate Limiting Implementation
Supports multiple strategies: fixed window, sliding window, and token bucket
"""

# import asyncio
import time
from collections import defaultdict

# from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, DefaultDict, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class FixedWindowRateLimiter:
    """Fixed window rate limiter - resets at fixed intervals"""

    def __init__(self, requests: int, window: int):
        """
        Args:
            requests: Number of requests allowed per window
            window: Time window in seconds
        """
        self.requests = requests
        self.window = window
        self.clients: DefaultDict[str, Dict[str, float]] = defaultdict(
            lambda: {"count": 0.0, "reset_time": 0.0}
        )

    def is_allowed(self, identifer: str) -> Tuple[bool, dict]:
        """Check if request is allowed and return rate limit info"""
        now = time.time()
        client = self.clients[identifer]

        # Reset window if expired
        if now >= client["reset_time"]:
            client["count"] = 0
            client["reset_time"] = now + self.window

        # Check if within limit
        if client["count"] < self.requests:
            client["count"] += 1
            return True, {
                "limit": self.requests,
                "remaining": self.requests - client["count"],
                "reset": int(client["reset_time"]),
            }

        return False, {
            "limit": self.requests,
            "remaining": 0,
            "reset": int(client["reset_time"]),
        }


class SlidingWindowRateLimiter:
    """Sliding window rate limiter - more accurate than fixed window"""

    def __init__(self, requests: int, window: int):
        self.requests = requests
        self.window = window
        self.clients: DefaultDict[str, List[float]] = defaultdict(list)

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """Check if request is allowed"""
        now = time.time()
        window_start = now - self.window

        # Remove expired timestamps
        self.clients[identifier] = [
            ts for ts in self.clients[identifier] if ts > window_start
        ]

        current_count = len(self.clients[identifier])

        if current_count < self.requests:
            self.clients[identifier].append(now)
            oldest_timestamp = (
                min(self.clients[identifier]) if self.clients[identifier] else now
            )
            reset_time = int(oldest_timestamp + self.window)

            return True, {
                "limit": self.requests,
                "remaining": self.requests - (current_count + 1),
                "reset": reset_time,
            }

        oldest_timestamp = min(self.clients[identifier])
        return False, {
            "limit": self.requests,
            "remaining": 0,
            "reset": int(oldest_timestamp + self.window),
        }


class TokenBucketRateLimiter:
    """Token bucket rate limiter - allows bursts"""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.clients: DefaultDict[str, Dict[str, float]] = defaultdict(
            lambda: {"tokens": float(capacity), "last_refill": time.time()}
        )

    def is_allowed(self, identifier: str) -> tuple[bool, dict]:
        """Check if request is allowed"""
        now = time.time()
        client = self.clients[identifier]

        # Refill tokens
        time_passed = now - client["last_refill"]
        new_tokens = time_passed * self.refill_rate
        client["tokens"] = min(float(self.capacity), client["tokens"] + new_tokens)
        client["last_refill"] = now

        # Check if token available
        if client["tokens"] >= 1:
            client["tokens"] -= 1
            return True, {
                "limit": self.capacity,
                "remaining": int(client["tokens"]),
                "reset": int(now + (1 / self.refill_rate)),
            }

        return False, {
            "limit": self.capacity,
            "remaining": 0,
            "reset": int(now + ((1 - client["tokens"]) / self.refill_rate)),
        }


# ============================================================================
# Rate Limiting Middleware & Decorators
# ============================================================================


class RateLimitMiddleware:
    """Global rate limiting middleware"""

    def __init__(self, app, get_identifier: Callable):
        self.app = app
        self.get_identifier = get_identifier

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive)

        # Access rate_limiter from app.state at request time, not at init time
        if not hasattr(request.app.state, "rate_limiter"):
            # If Redis isn't ready yet, allow the request
            await self.app(scope, receive, send)
            return

        limiter = request.app.state.rate_limiter
        identifier = self.get_identifier(request)
        allowed, info = await limiter.is_allowed(identifier)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"X-RateLimit-Limit", str(info["limit"]).encode()),
                        (b"X-RateLimit-Remaining", str(info["remaining"]).encode()),
                        (b"X-RateLimit-Reset", str(info["reset"]).encode()),
                    ]
                )
                message["headers"] = headers
            await send(message)

        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["reset"] - int(time.time())),
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send_with_headers)


async def rate_limit(limiter, get_identifier: Optional[Callable] = None):
    """Decorator for rate limiting specific endpoints"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request and "request" in kwargs:
                request = kwargs["request"]

            if not request:
                raise ValueError("Request object not found in endpoint")

            # Get identifier
            if get_identifier:
                identifier = get_identifier(request)
            else:
                identifier = request.client.host

            # Check rate limit
            allowed, info = limiter.is_allowed(identifier)

            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(info["limit"]),
                        "X-RateLimit-Remaining": str(info["remaining"]),
                        "X-RateLimit-Reset": str(info["reset"]),
                        "Retry-After": str(info["reset"] - int(time.time())),
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
