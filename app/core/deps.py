from typing import List

from fastapi import Depends, Request, status
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.redis import token_in_blocklist
from app.core.security import JWTHandler, TokenData
from app.crud.users import UserCRUD
from app.db.session import get_session
from app.models.users import User

user_crud = UserCRUD()


class TokenBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True) -> None:
        super().__init__(scheme_name="Bearer", auto_error=auto_error)

    async def __call__(self, request: Request) -> TokenData:
        creds: HTTPAuthorizationCredentials | None = await super().__call__(request)

        if creds is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Authorization credentials not provided",
                    "revolution": "please provide a valid token",
                },
            )

        token = creds.credentials
        token_data = JWTHandler.decode_token(token)

        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Token invalid or expired",
                    "revolution": "please get new token",
                },
            )
        if await token_in_blocklist(token_data["jti"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Token invalid or revoked",
                    "revolution": "please get new token",
                },
            )
        self.verify_token_data(token_data)
        return token_data

    def verify_token_data(self, token_data: TokenData) -> None:
        raise NotImplementedError("Please override this method in child classes")


class AccessTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: TokenData) -> None:
        if token_data and token_data["refresh"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please provide and access token",
            )


class RefreshTokenBearer(TokenBearer):
    def verify_token_data(self, token_data: TokenData) -> None:
        if token_data and not token_data["refresh"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please provide and refresh token",
            )


async def get_current_user(
    token_details: TokenData = Depends(AccessTokenBearer()),  # noqa: B008
    session: AsyncSession = Depends(get_session),  # noqa: B008
) -> User:
    # user_username = token_details['user']['username']
    user_uid = token_details["user"]["uid"]
    user = await user_crud.get_user_by_uid(session, user_uid)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> User:
    if not current_user.is_active or not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive or unverified user",
        )
    return current_user


class RoleChecker:
    def __init__(self, allowed_roles: List[str]) -> None:
        self.allowed_roles = allowed_roles

    def __call__(
        self, current_user: User = Depends(get_current_active_user)  # noqa: B008
    ) -> User:
        if current_user.role in self.allowed_roles:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not allowed to perform this action",
        )
