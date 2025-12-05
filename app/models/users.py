import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy.dialects.postgresql as pg
from pydantic import EmailStr
from sqlmodel import Column, Field, SQLModel, String

from app.enums.roles import UserRole
from sqlmodel import Column, Field, Relationship, SQLModel

from app.models.streams import Stream


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserBase(SQLModel):
    username: str = Field(min_length=3, index=True, nullable=False, unique=True)
    email: EmailStr = Field(index=True, nullable=False, unique=True)
    first_name: Optional[str] = Field(default=None, nullable=True)
    last_name: Optional[str] = Field(max_length=20, default=None, nullable=True)
    is_active: bool = Field(default=False)
    is_verified: bool = Field(default=False)
    role: str = Field(
        sa_column=Column(String, nullable=True),
        default=UserRole.VIEWER,
    )


class User(UserBase, table=True):
    __tablename__ = "users"

    uid: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, nullable=False
    )

    activation_token: Optional[str] = Field(default=None)
    reset_token: Optional[str] = Field(default=None)

    reset_token_expires_at: Optional[datetime] = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True)
    )

    password_hash: str = Field(exclude=True)

    created_at: datetime = Field(
        sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=False),
        default_factory=lambda: datetime.now(timezone.utc),
    )

    updated_at: datetime = Field(
        sa_column=Column(
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            default=utc_now,
            onupdate=utc_now,
        )
    )

    streams: Optional[list["Stream"]] = Relationship(back_populates="user")


class Token(SQLModel, table=True):
    __tablename__ = "tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.uid", nullable=False)
    token: str = Field(nullable=False, unique=True)

    created_at: datetime = Field(default_factory=utc_now, nullable=False)
    expires_at: datetime = Field(nullable=False)
