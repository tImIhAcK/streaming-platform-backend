from datetime import datetime, timezone

# from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.models.streams import Stream


class StreamService:
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
