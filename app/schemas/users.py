import uuid
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr

from app.enums.roles import UserRole


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: str

    role: UserRole = UserRole.VIEWER


class PublicUserCreate(UserCreate):
    role: Literal[UserRole.VIEWER, UserRole.STREAMER] = UserRole.VIEWER


class AdminUserCreate(UserCreate):
    role: UserRole = UserRole.ADMIN


class UserRead(BaseModel):
    uid: uuid.UUID
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    role: UserRole


class UserReadWithToken(UserRead):
    activation_token: Optional[str] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[UserRole] = None


class TokenRead(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str
    new_password: str
