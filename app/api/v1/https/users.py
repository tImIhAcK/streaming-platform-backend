from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import get_current_active_user
from app.schemas.users import UserRead

users_router = APIRouter(tags=["users"])


@users_router.get("/me", response_model=UserRead, status_code=200)
async def read_me(
    current_user: Annotated[UserRead, Depends(get_current_active_user)],
) -> UserRead:
    return current_user
