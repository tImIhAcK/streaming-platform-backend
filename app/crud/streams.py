from typing import List, Optional

# from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import desc, not_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.crud.base import BaseCRUD
from app.models.streams import Stream

# from app.models.users import User
from app.schemas.streams import StreamCreate, StreamUpdate


class StreamCrud(BaseCRUD[Stream]):

    def __init__(self) -> None:
        super().__init__(Stream)

    async def create_stream(
        self,
        session: AsyncSession,
        user_id: str,
        stream_data: StreamCreate,
    ) -> Stream:

        stream_key = Stream.generate_stream_key()
        new_stream = Stream(
            user_id=user_id,
            title=stream_data.title,
            description=stream_data.description,
            category=stream_data.category,
            is_private=stream_data.is_private,
            stream_key=stream_key,
            rtmp_url=f"{settings.RTMP_BASE_URL}/{stream_key}",
            hls_url=f"{settings.HLS_BASE_URL}/{stream_key}/index.m3u8",
        )
        created_stream = await self.create(session, new_stream)
        return created_stream

    async def get_stream_by_id(
        self, session: AsyncSession, stream_id: str
    ) -> Optional[Stream]:
        """Get stream by ID"""
        return await self.get(session, stream_id, field="sid")

    async def get_stream_by_key(
        self, session: AsyncSession, stream_key: str
    ) -> Optional[Stream]:
        """Get stream by stream key"""
        return await self.get(Stream, stream_key, "stream_key")

    @staticmethod
    async def get_streams_by_user(
        session: AsyncSession, user_id: str, skip: int = 0, limit: int = 10
    ) -> List[Stream]:
        """Get all streams for a user"""
        stmt = (
            select(Stream)
            .where(Stream.user_id == user_id)
            .order_by(desc(Stream.created_at))
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_live_streams(
        session: AsyncSession, skip: int = 0, limit: int = 20
    ) -> List[Stream]:
        """Get all current live stream"""
        stmt = (
            select(Stream)
            .where(Stream.is_live, not_(Stream.is_private))
            .order_by(desc(Stream.current_viewers))
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def update_stream(
        self,
        session: AsyncSession,
        stream_id: str,
        stream_data: StreamUpdate,
    ) -> Optional[Stream]:
        data = stream_data.model_dump(exclude_unset=True)
        updated_stream = await self.update(session, stream_id, data, field="sid")
        return updated_stream if updated_stream else None

    async def delete_stream(self, session: AsyncSession, stream_id: str) -> bool:
        return await self.delete(session, stream_id, field="sid")
