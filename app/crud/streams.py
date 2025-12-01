from datetime import datetime, timezone
from typing import List, Optional

# from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import desc, not_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.exceptions import ResourceNotFoundException, ValidationException
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
        return await self.get(session, stream_key, "stream_key")

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

    @staticmethod
    async def start_stream(
        session: AsyncSession, stream_id: str, user_id: str
    ) -> Stream:
        result = await session.execute(
            select(Stream).where(Stream.sid == stream_id, Stream.user_id == user_id)
        )
        stream: Stream | None = result.scalars().first()

        if not stream:
            raise ResourceNotFoundException(
                resource_id=stream_id, resource_type="Stream"
            )

        if stream.is_live:
            raise ValidationException(message="Stream is already live")

        stream.is_live = True
        stream.started_at = datetime.now(timezone.utc)
        stream.ended_at = None
        stream.current_viewers = 0

        await session.commit()
        await session.refresh(stream)
        return stream

    @staticmethod
    async def stop_stream(
        session: AsyncSession, stream_id: str, user_id: str
    ) -> Stream:
        result = await session.execute(
            select(Stream).where(Stream.sid == stream_id, Stream.user_id == user_id)
        )
        stream: Stream | None = result.scalars().first()

        if not stream:
            raise ResourceNotFoundException(
                resource_id=stream_id, resource_type="Stream"
            )

        if not stream.is_live:
            raise ValidationException(message="Stream is not live")

        stream.is_live = False
        stream.ended_at = datetime.now(timezone.utc)
        stream.current_viewers = 0

        await session.commit()
        await session.refresh(stream)
        return stream

    @staticmethod
    async def update_viewer_count(
        session: AsyncSession, stream_id: str, viewer_count: int
    ):
        result = await session.execute(select(Stream).where(Stream.sid == stream_id))
        stream = result.scalars().first()

        if stream:
            stream.current_viewers = viewer_count
            if viewer_count > stream.peak_viewers:
                stream.peak_viewers = viewer_count
            await session.commit()

    @staticmethod
    async def increment_total_views(session: AsyncSession, stream_id: str):
        result = await session.execute(select(Stream).where(Stream.sid == stream_id))
        stream = result.scalars().first()

        if stream:
            stream.total_views += 1
            await session.commit()
