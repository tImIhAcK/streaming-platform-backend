"""
Nginx-RTMP webhook handlers
These endpoints are called by Nginx-RTMP server
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import UnauthorizedException
from app.crud.streams import StreamCrud
from app.db.session import get_session
from app.services.streams import StreamService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["stream-webhooks"])

stream_service = StreamService()
stream_crud = StreamCrud()


@router.post("/auth/publish")
async def authenticate_publish(
    key: Annotated[str, Form(...)],  # Stream key
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Authenticate RTMP publish request
    Called by Nginx-RTMP when someone tries to publish
    """
    logger.info(f"Publish auh request for stream key: {key}")

    stream = await stream_crud.get_stream_by_key(session, key)

    if not stream:
        logger.warning(f"Invalid stream key attempted: {key}")
        raise UnauthorizedException(message="Invalid stream key")

    logger.info(f"Stream authenticated: {stream.sid} - {stream.title}")
    return {"status": "ok"}


@router.post("/webhook/publish_done")
async def on_publish_done(
    key: Annotated[str, Form(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Called when publishing starts successfully
    """
    logger.info(f"Stream started: {key}")

    stream = await stream_crud.get_stream_by_key(session, key)
    if stream and not stream.is_live:
        await stream_service.start_stream(session, str(stream.sid), str(stream.user_id))

    return {"status": "ok"}


@router.post("/webhook/done")
async def on_stream_done(
    key: Annotated[str, Form(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Called when stream ends
    """
    logger.info(f"Stream ends: {key}")

    stream = await stream_crud.get_stream_by_key(session, key)
    if stream and stream.is_live:
        await stream_service.stop_stream(session, str(stream.sid), str(stream.user_id))

    return {"status": "ok"}


@router.post("/webhook/play")
async def on_play(
    key: Annotated[str, Form(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Called when a viewer starts watching
    """
    stream = await stream_crud.get_stream_by_key(session, key)
    if stream:
        # Increment viewer count
        await stream_service.update_viewer_count(
            session, str(stream.sid), stream.current_views + 1
        )
        # Increment total views
        await stream_service.increment_total_views(session, str(stream.sid))

    return {"status": "ok"}


@router.post("/webhook/play_done")
async def on_play_done(
    key: Annotated[str, Form(...)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """
    Called when a viewer stops watching
    """
    stream = await stream_crud.get_stream_by_key(session, key)
    if stream and stream.current_viewers > 0:
        # Decrement viewer count
        await stream_service.update_viewer_count(
            session, str(stream.sid), stream.current_views - 1
        )

    return {"status": "ok"}
