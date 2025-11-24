from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio.session import AsyncSession

from .base import async_engine


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = async_sessionmaker(
        bind=async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session() as ses:
        yield ses
