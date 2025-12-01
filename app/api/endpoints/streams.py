from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, status

# from fastapi.exceptions import HTTPException
# from fastapi.responses import JSONResponse
from sqlmodel.ext.asyncio.session import AsyncSession

# from app.core.config import settings
from app.core.deps import get_current_active_user
from app.core.exceptions import ResourceNotFoundException
from app.core.role_checker import (  # viewer_role_checker,
    admin_role_checker,
    moderator_role_checker,
    streamer_role_checker,
)
from app.crud.streams import StreamCrud
from app.db.session import get_session
from app.models.users import User
from app.schemas.streams import (  # StreamStartRequest,; StreamStopRequest,
    StreamCreate,
    StreamPublicResponse,
    StreamResponse,
    StreamUpdate,
)

stream_router = APIRouter(tags=["streams"])
stream_crud = StreamCrud()


@stream_router.post(
    "/",
    response_model=StreamResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[admin_role_checker, streamer_role_checker],
)
async def create_stream(
    stream_data: StreamCreate,
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
) -> StreamResponse:
    stream = await stream_crud.create_stream(
        session, str(current_user.uid), stream_data
    )
    return stream


@stream_router.get("/live", response_model=List[StreamPublicResponse])
async def get_live_streams(
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    skip: int = 0,
    limit: int = 100,
) -> List[StreamPublicResponse]:
    streams = await stream_crud.get_live_streams(session, skip, limit)
    return streams


@stream_router.get(
    "/my-streams",
    response_model=List[StreamResponse],
    dependencies=[streamer_role_checker, admin_role_checker],
)
async def get_my_streams(
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    skip: int = 0,
    limit: int = 0,
    current_user=Annotated[User, Depends(get_current_active_user)],  # noqa: B008
) -> List[StreamResponse]:
    streams = await stream_crud.get_streams_by_user(
        session, str(current_user.uid), skip, limit
    )
    return streams


@stream_router.get("/{stream_id}", response_model=Optional[StreamPublicResponse])
async def get_stream(
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    stream_id: Annotated[str, Query(...)],  # noqa: B008
) -> Optional[StreamPublicResponse]:
    stream = await stream_crud.get_stream_by_id(session, stream_id)
    if not stream:
        ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")
    return stream


@stream_router.get(
    "/{stream_id}/details",
    response_model=Optional[StreamResponse],
    dependencies=[streamer_role_checker, admin_role_checker, moderator_role_checker],
)
async def get_stream_details(
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    stream_id: Annotated[str, Query(...)],  # noqa: B008
) -> Optional[StreamResponse]:
    stream = await stream_crud.get_stream_by_id(session, stream_id)
    if not stream:
        ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")
    return stream


@stream_router.put(
    "/{stream_id}",
    response_model=StreamResponse,
    dependencies=[admin_role_checker, streamer_role_checker],
)
async def update_stream(
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    stream_id: Annotated[str, Query(...)],  # noqa: B008
    stream_data: StreamUpdate,
    current_user=Annotated[User, Depends(get_current_active_user)],  # noqa: B008
) -> StreamResponse:
    stream = await stream_crud.update_stream(
        session, stream_id, str(current_user.uid), stream_data
    )
    if not stream:
        raise ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")

    return stream


@stream_router.delete(
    "/{stream_id}",
    status_code=204,
    dependencies=[admin_role_checker, streamer_role_checker],
)
async def delete_stream(
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    current_user: Annotated["User", Depends(get_current_active_user)],  # noqa: B008
    stream_id: str,
):
    deleted = await stream_crud.delete_stream(
        session=session,
        stream_id=stream_id,
        user_id=str(current_user.uid),
    )

    if not deleted:
        raise ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")

    return None
