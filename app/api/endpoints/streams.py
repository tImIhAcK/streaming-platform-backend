from typing import Annotated, List, Optional, Set

from fastapi import APIRouter, Depends, Path, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ResourceNotFoundException
from app.core.permissions import PermissionChecker
from app.crud.streams import StreamCrud
from app.db.session import get_session
from app.enums.permissions import Permission
from app.models.users import User
from app.schemas.streams import (
    StreamCreate,
    StreamPublicResponse,
    StreamResponse,
    StreamUpdate,
)

stream_router = APIRouter(tags=["streams"])
stream_crud = StreamCrud()


# --- Generalized permission dependency ---
def require_permissions(permissions: Set[Permission], mode: str = "all"):
    """Returns a dependency that checks if current_user has the required permissions."""
    return Depends(PermissionChecker(permissions, mode=mode))


# --- Endpoints ---
@stream_router.post(
    "/",
    response_model=StreamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_stream(
    stream_data: StreamCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[
        User,
        require_permissions(
            {Permission.CREATE_STREAM, Permission.CONFIGURE_STREAM}, mode="all"
        ),
    ],
) -> StreamResponse:
    """Create a new stream"""
    return await stream_crud.create_stream(session, str(current_user.uid), stream_data)


@stream_router.get("/live", response_model=List[StreamPublicResponse])
async def get_live_streams(
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> List[StreamPublicResponse]:
    """Get all currently live streams"""
    return await stream_crud.get_live_streams(session, skip, limit)


@stream_router.get(
    "/my-streams",
    response_model=List[StreamResponse],
)
async def get_my_streams(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, require_permissions({Permission.READ_STREAM})],
    skip: int = 0,
    limit: int = 0,
) -> List[StreamResponse]:
    return await stream_crud.get_streams_by_user(
        session, str(current_user.uid), skip, limit
    )


@stream_router.get("/{stream_id}", response_model=Optional[StreamPublicResponse])
async def get_stream(
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
) -> Optional[StreamPublicResponse]:
    stream = await stream_crud.get_stream_by_id(session, stream_id)
    if not stream:
        raise ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")
    return stream


@stream_router.get(
    "/{stream_id}/details",
    response_model=Optional[StreamResponse],
)
async def get_stream_details(
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    current_user: Annotated[User, require_permissions({Permission.READ_STREAM})],
) -> Optional[StreamResponse]:
    stream = await stream_crud.get_stream_by_id(session, stream_id)
    if not stream:
        raise ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")
    return stream


@stream_router.put(
    "/{stream_id}",
    response_model=StreamResponse,
)
async def update_stream(
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    stream_data: StreamUpdate,
    current_user: Annotated[User, require_permissions({Permission.UPDATE_STREAM})],
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
)
async def delete_stream(
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    current_user: Annotated[User, require_permissions({Permission.DELETE_STREAM})],
):
    deleted = await stream_crud.delete_stream(
        session=session, stream_id=stream_id, user_id=str(current_user.uid)
    )
    if not deleted:
        raise ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")
    return None


@stream_router.post(
    "/{stream_id}/start",
    response_model=StreamResponse,
)
async def start_stream(
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    current_user: Annotated[
        User,
        require_permissions(
            {Permission.START_STREAM, Permission.UPDATE_STREAM}, mode="any"
        ),
    ],
) -> StreamResponse:
    return await stream_crud.start_stream(session, stream_id, str(current_user.uid))


@stream_router.post(
    "/{stream_id}/stop",
    response_model=StreamResponse,
)
async def stop_stream(
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    current_user: Annotated[
        User,
        require_permissions(
            {Permission.STOP_STREAM, Permission.UPDATE_STREAM}, mode="any"
        ),
    ],
) -> StreamResponse:
    return await stream_crud.stop_stream(session, stream_id, str(current_user.uid))
