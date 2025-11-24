from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.crud.users import UserCRUD
from app.enums.users import UserRole
from app.schemas.users import AdminUserCreate, UserUpdate


async def init_db(session: AsyncSession) -> None:
    user_crud = UserCRUD()

    user_in = AdminUserCreate(
        username=settings.SUPERUSER_USERNAME,
        first_name="Admin",
        last_name="Admin",
        password=settings.SUPERUSER_PASSWORD,
        email=settings.SUPERUSER_EMAIL,
        role=UserRole.ADMIN,
    )
    user_exist = await user_crud.user_exists(
        session,
        username=settings.SUPERUSER_USERNAME,
        email=settings.SUPERUSER_EMAIL,
    )

    if not user_exist:
        admin_user = await user_crud.create_user(session, user_in)
        update_user = UserUpdate(is_active=True, is_verified=True)
        _ = await user_crud.update_user(session, str(admin_user.uid), update_user)
