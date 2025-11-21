
import logging
import signal
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRoute
from app.core.config import settings
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress noisy libraries
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate unique ID for OpenAPI documentation"""
    return f"{route.tags[0]}-{route.name}" if route.tags else route.name



# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     Handles startup and shutdown lifecycle events.
#     Ensures database connections and background resources are cleanly managed.
#     """
#     # ✅ Startup
#     try:
#         logger.info("🚀 Starting application initialization...")
#         await init_db()
#         logger.info("✅ Database initialized")
        
#         # Test Celery connection
#         celery_ping = celery_app.control.ping()
#         if celery_ping:
#             logger.info("✅ Celery broker is reachable")
#         else:
#             logger.warning("⚠️ Celery broker may be unreachable")
        
#         logger.info("🚀 Application startup complete.")
#     except Exception as e:
#         logger.error(f"❌ Startup error: {e}", exc_info=True)
#         raise
    
#     yield

#     # ✅ Shutdown
#     try:
#         logger.info("🛑 Starting graceful shutdown...")
#         await close_db()
#         logger.info("🛑 Application shutdown complete.")
#     except Exception as e:
#         logger.error(f"❌ Shutdown error: {e}", exc_info=True)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A Streaming Platform API",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    generate_unique_id_function=custom_generate_unique_id,
    # lifespan=lifespan,
)


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
    logger.info(f"✅ CORS configured for: {settings.all_cors_origins}")
else:
    logger.warning("⚠️ CORS not configured - no origins allowed")


# 🧩 Register all API routes
# app.include_router(router)


# 🏥 Health Check Endpoints
@app.get("/health", tags=["health"])
async def health_check():
    """Basic health check endpoint"""
    return {"status": "healthy", "service": settings.APP_NAME}


@app.get("/health/ready", tags=["health"])
async def readiness_check():
    """Readiness check - returns 200 only if app is ready to serve requests"""
    try:
        # Add any critical checks here
        return {"status": "ready"}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {"status": "not_ready", "error": str(e)}, 503


@app.get("/", tags=["root"])
async def root():
    """Root endpoint - API information"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": "0.1.0",
        "docs": f"{settings.API_V1_STR}/docs",
    }


# 🔧 Signal Handlers for graceful shutdown
def signal_handler(signum, frame):
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
