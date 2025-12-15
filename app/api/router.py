from fastapi import APIRouter

from app.api.v1.https import auth, streams, users
from app.api.v1.webhooks import stream_webhooks
from app.core.config import settings

routes = APIRouter()

routes.include_router(auth.auth_router, prefix=f"{settings.API_V1_STR}/auth")
routes.include_router(users.users_router, prefix=f"{settings.API_V1_STR}/users")
routes.include_router(streams.stream_router, prefix=f"{settings.API_V1_STR}/streams")
routes.include_router(stream_webhooks.router, prefix=f"{settings.API_V1_STR}/streams")
