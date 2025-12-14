from typing import Annotated, List, Optional, Set

from fastapi import APIRouter, Depends, Path, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.exceptions import ResourceNotFoundException
from app.core.permissions import PermissionChecker
from app.core.redis_rate_limiter import redis_rate_limit
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
from app.services.streams import StreamService
from app.utils.helper import get_user_identifier

stream_router = APIRouter(tags=["streams"])
stream_crud = StreamCrud()
stream_service = StreamService()


# --- Generalized permission dependency ---
def require_permissions(permissions: Set[Permission], mode: str = "all"):
    """Returns a dependency that checks if current_user has the required permissions."""
    return Depends(PermissionChecker(permissions, mode=mode))


# --- Endpoints ---


# Heavy operation - strict limit: 2 streams created per minute
@stream_router.post(
    "/",
    response_model=StreamResponse,
    status_code=status.HTTP_201_CREATED,
)
@redis_rate_limit(
    capacity=2,
    refill_rate=0.033,
    prefix="stream_create:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def create_stream(
    request: Request,
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


# Public read - lenient: 100 per minute
@stream_router.get("/live", response_model=List[StreamPublicResponse])
@redis_rate_limit(
    capacity=100,
    refill_rate=1.67,
    prefix="stream_live:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def get_live_streams(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    skip: int = 0,
    limit: int = 100,
) -> List[StreamPublicResponse]:
    """Get all currently live streams"""
    return await stream_crud.get_live_streams(session, skip, limit)


# Authenticated read - moderate: 30 per minute
@stream_router.get(
    "/my-streams",
    response_model=List[StreamResponse],
)
@redis_rate_limit(
    capacity=30,
    refill_rate=0.5,
    prefix="stream_my:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def get_my_streams(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, require_permissions({Permission.READ_STREAM})],
    skip: int = 0,
    limit: int = 0,
) -> List[StreamResponse]:
    return await stream_crud.get_streams_by_user(
        session, str(current_user.uid), skip, limit
    )


# Public read by ID - lenient: 60 per minute
@stream_router.get("/{stream_id}", response_model=Optional[StreamPublicResponse])
@redis_rate_limit(
    capacity=60,
    refill_rate=1.0,
    prefix="stream_get:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def get_stream(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
) -> Optional[StreamPublicResponse]:
    stream = await stream_crud.get_stream_by_id(session, stream_id)
    if not stream:
        raise ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")
    return stream


# Authenticated detailed read - moderate: 30 per minute
@stream_router.get(
    "/{stream_id}/details",
    response_model=Optional[StreamResponse],
)
@redis_rate_limit(
    capacity=30,
    refill_rate=0.5,
    prefix="stream_details:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def get_stream_details(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    current_user: Annotated[User, require_permissions({Permission.READ_STREAM})],
) -> Optional[StreamResponse]:
    stream = await stream_crud.get_stream_by_id(session, stream_id)
    if not stream:
        raise ResourceNotFoundException(resource_id=stream_id, resource_type="Stream")
    return stream


# Update operation - moderate: 10 per minute
@stream_router.put(
    "/{stream_id}",
    response_model=StreamResponse,
)
@redis_rate_limit(
    capacity=10,
    refill_rate=0.167,
    prefix="stream_update:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def update_stream(
    request: Request,
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


# Delete operation - strict: 5 per 5 minutes
@stream_router.delete(
    "/{stream_id}",
    status_code=204,
)
@redis_rate_limit(
    capacity=5,
    refill_rate=0.0167,
    prefix="stream_delete:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def delete_stream(
    request: Request,
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


# Critical operation - strict: 5 starts per minute
@stream_router.post(
    "/{stream_id}/start",
    response_model=StreamResponse,
)
@redis_rate_limit(
    capacity=5,
    refill_rate=0.083,
    prefix="stream_start:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def start_stream(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    current_user: Annotated[
        User,
        require_permissions(
            {Permission.START_STREAM, Permission.UPDATE_STREAM}, mode="any"
        ),
    ],
) -> StreamResponse:
    return await stream_service.start_stream(session, stream_id, str(current_user.uid))


# Critical operation - strict: 5 stops per minute
@stream_router.post(
    "/{stream_id}/stop",
    response_model=StreamResponse,
)
@redis_rate_limit(
    capacity=5,
    refill_rate=0.083,
    prefix="stream_stop:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def stop_stream(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    stream_id: Annotated[str, Path(...)],
    current_user: Annotated[
        User,
        require_permissions(
            {Permission.STOP_STREAM, Permission.UPDATE_STREAM}, mode="any"
        ),
    ],
) -> StreamResponse:
    return await stream_service.stop_stream(session, stream_id, str(current_user.uid))
