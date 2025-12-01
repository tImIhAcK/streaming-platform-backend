from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, Type, TypeVar, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseCRUD(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def create(self, session: AsyncSession, obj_in: ModelType) -> ModelType:
        session.add(obj_in)
        try:
            await session.commit()
            await session.refresh(obj_in)
            return obj_in
        except SQLAlchemyError as e:
            await session.rollback()
            raise e

    async def get(
        self, session: AsyncSession, value: Any, field: str = "id"
    ) -> Optional[ModelType]:
        query = select(self.model).where(getattr(self.model, field) == value)
        result = await session.execute(query)
        return cast(Optional[ModelType], result.scalar_one_or_none())

    async def get_all(
        self, session: AsyncSession, skip: int = 0, limit: int = 20
    ) -> List[ModelType]:
        result = await session.execute(select(self.model).offset(skip).limit(limit))
        return cast(List[ModelType], result.scalars().all())

    async def update(
        self, session: AsyncSession, value: Any, data: dict, field: str = "id"
    ) -> Optional[ModelType]:
        result = await session.execute(
            select(self.model).where(getattr(self.model, field) == value)
        )
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return None

        for key, value_ in data.items():
            setattr(db_obj, key, value_)

        if hasattr(db_obj, "updated_at"):
            db_obj.updated_at = datetime.now(timezone.utc)

        try:
            session.add(db_obj)
            await session.commit()
            await session.refresh(db_obj)
            return cast(Optional[ModelType], db_obj)
        except SQLAlchemyError as e:
            await session.rollback()
            raise e

    async def delete(
        self, session: AsyncSession, value: Any, field: str = "id"
    ) -> bool:
        result = await session.execute(
            select(self.model).where(getattr(self.model, field) == value)
        )
        db_obj = result.scalar_one_or_none()
        if not db_obj:
            return False
        try:
            await session.delete(db_obj)
            await session.commit()
            return True
        except SQLAlchemyError:
            await session.rollback()
            return False
