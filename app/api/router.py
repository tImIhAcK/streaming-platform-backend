from fastapi import APIRouter

from app.api.endpoints import auth
from app.core.config import settings

routes = APIRouter()

routes.include_router(auth.auth_router, prefix=f"{settings.API_V1_STR}/auth")
