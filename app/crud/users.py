from typing import Optional

from pydantic import EmailStr
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import generate_token, get_password_hash
from app.crud.base import BaseCRUD
from app.models.users import User
from app.schemas.users import UserCreate, UserRead, UserUpdate


class UserCRUD(BaseCRUD[User]):
    def __init__(self) -> None:
        super().__init__(User)

    async def get_by_uid(self, session: AsyncSession, uid: str) -> Optional[UserRead]:
        user = await self.get(session, uid, field="uid")
        return UserRead.model_validate(user) if user else None

    async def get_user_by_uid(self, session: AsyncSession, uid: str) -> Optional[User]:
        return await self.get(session, uid, field="uid")

    async def get_by_username(
        self, session: AsyncSession, username: str
    ) -> Optional[UserRead]:
        user = await self.get(session, username, field="username")
        return UserRead.model_validate(user) if user else None

    async def get_user_for_auth(
        self, session: AsyncSession, username: str
    ) -> Optional[User]:
        return await self.get(session, username, field="username")

    async def get_by_email(
        self, session: AsyncSession, email: EmailStr
    ) -> Optional[UserRead]:
        user = await self.get(session, email, field="email")
        return UserRead.model_validate(user) if user else None

    async def create_user(self, session: AsyncSession, user_in: UserCreate) -> User:
        data = user_in.model_dump()
        new_user = User(**data)
        new_user.password_hash = get_password_hash(user_in.password)
        new_user.activation_token = generate_token()
        new_user.is_active = True
        created_user = await self.create(session, new_user)
        return created_user

    async def user_exists(
        self, session: AsyncSession, username: str, email: EmailStr
    ) -> bool:
        statement = select(User).where(
            (User.username == username) | (User.email == email)
        )
        result = await session.execute(statement)
        user = result.first()
        return user is not None

    async def get_users(
        self, session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> list[UserRead]:
        statement = select(User).offset(skip).limit(limit)
        result = await session.execute(statement)
        users = result.scalars().all()
        return [UserRead.model_validate(user) for user in users]

    async def update_user(
        self, session: AsyncSession, uid: str, user_in: UserUpdate
    ) -> Optional[UserRead]:
        data = user_in.model_dump(exclude_unset=True)
        updated_user = await self.update(session, uid, data, field="uid")
        return UserRead.model_validate(updated_user) if updated_user else None

    async def delete_user(self, session: AsyncSession, uid: str) -> bool:
        return await self.delete(session, uid, field="uid")

    async def get_by_activation_token(
        self, session: AsyncSession, token: str
    ) -> Optional[UserRead]:
        user = await self.get(session, token, field="activation_token")
        return UserRead.model_validate(user) if user else None
