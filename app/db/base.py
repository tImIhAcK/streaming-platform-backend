from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import create_engine

from app.core.config import settings

async_engine = AsyncEngine(create_engine(url=settings.DATABASE_URL))
