import uuid

# from datetime import datetime
from typing import List, Optional, cast

from sqlmodel import desc, not_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.models.streams import Stream

# from app.models.users import User
from app.schemas.streams import StreamCreate  # StreamUpdate


class StreamService:

    @staticmethod
    async def create_stream(
        session: AsyncSession,
        user_id: uuid.UUID,
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
        session.add(new_stream)
        await session.commit()
        await session.refresh(new_stream)
        return new_stream

    @staticmethod
    async def get_stream_by_id(
        session: AsyncSession, stream_id: uuid.UUID
    ) -> Optional[Stream]:
        """Get stream by ID"""
        result = await session.get(Stream, stream_id)
        return cast(Optional[Stream], result)

    @staticmethod
    async def get_stream_by_key(
        session: AsyncSession, stream_key: str
    ) -> Optional[Stream]:
        """Get stream by stream key"""
        result = await session.get(Stream, stream_key)
        return cast(Optional[Stream], result)

    @staticmethod
    async def get_streams_by_user(
        session: AsyncSession, user_id: uuid.UUID, skip: int = 0, limit: int = 10
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

    # @staticmethod
    # async def update_stream
