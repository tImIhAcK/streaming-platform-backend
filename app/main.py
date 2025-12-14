import logging
import signal
from contextlib import asynccontextmanager

# from contextlib import asynccontextmanager
from typing import Any, Dict, Tuple, Union

import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

# from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import routes
from app.core.config import settings
from app.core.exceptions import AppException, app_exception_handler
from app.core.rate_limiter import (  # FixedWindowRateLimiter,; SlidingWindowRateLimiter,; TokenBucketRateLimiter,
    RateLimitMiddleware,
)
from app.core.redis_rate_limiter import RedisTokenBucketRateLimiter
from app.utils.helper import get_user_identifier

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress noisy libraries
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate unique ID for OpenAPI documentation"""
    if route.tags:
        first_tag: str = str(route.tags[0])
        return f"{first_tag}-{route.name}"
    return str(route.name)


_redis_client = None
# _redis_rate_limiter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_url = settings.REDIS_URL
    app.state.redis = redis.from_url(redis_url, decode_responses=True)

    try:
        await app.state.redis.ping()
        logger.info("Connected to Redis for rate limiting")
    except Exception as e:
        logger.info(f"⚠️ Redis unavailable, rate limiting will fail open: {e}")

    # Create global Redis rate limiter
    app.state.rate_limiter = RedisTokenBucketRateLimiter(
        redis_client=app.state.redis,
        capacity=60,  # 60 requests
        refill_rate=1.0,  # 1 request per sec = 60/min
        prefix="ratelimit:",
    )

    # Yield to run the application
    yield

    # ---------------------------
    # SHUTDOWN
    # ---------------------------
    if app.state.redis:
        try:
            await app.state.redis.close()
            print("✅ Redis connection closed")
        except Exception as e:
            print(f"⚠️ Error closing Redis: {e}")


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A Streaming Platform API",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
    generate_unique_id_function=custom_generate_unique_id,
)

# Register middleware with limiter
app.add_middleware(
    RateLimitMiddleware,
    get_identifier=get_user_identifier,
)

logger.info("✅ Redis RateLimitMiddleware enabled")


# 📂 Static Files Configuration
try:
    app.mount("/media", StaticFiles(directory="media"), name="media")
    logger.info("✅ Static files mounted at /media")
except Exception as e:
    logger.warning(f"⚠️ Failed to mount static files: {e}")


# 🔒 Security Middlewares (order matters - add before CORS)
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )
    logger.info("✅ TrustedHost middleware added")


# 🌍 CORS Configuration
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )
    cors_origins = settings.all_cors_origins
    logger.info(f"✅ CORS configured for: {cors_origins}")
else:
    logger.warning("⚠️ CORS not configured - no origins allowed")


@app.exception_handler(AppException)
async def custom_app_exception_handler(
    request: Request, exc: AppException
) -> JSONResponse:
    return await app_exception_handler(request, exc)


app.include_router(routes)


# 🏥 Health Check Endpoints
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint"""
    return {"status": "healthy", "service": settings.APP_NAME}


@app.get("/health/ready", tags=["health"])
async def readiness_check() -> Union[Dict[str, str], Tuple[Dict[str, str], int]]:
    """Readiness check - returns 200 only if ready"""
    try:
        # Add any critical checks here
        return {"status": "ready"}
    except Exception as e:
        error_msg = f"Readiness check failed: {e}"
        logger.error(error_msg)
        return {"status": "not_ready", "error": str(e)}, 503


@app.get("/", tags=["root"])
async def root() -> Dict[str, str]:
    """Root endpoint - API information"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": "0.1.0",
        "docs": f"{settings.API_V1_STR}/docs",
    }


# 🔧 Signal Handlers for graceful shutdown
def signal_handler(signum: int, frame: Any) -> None:
    """Handle termination signals gracefully"""
    signal_name = signal.Signals(signum).name
    logger.info(f"📌 Received {signal_name} signal")
    raise SystemExit(0)


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        reload=settings.ENVIRONMENT != "production",
        log_level=settings.LOG_LEVEL.lower(),
    )
