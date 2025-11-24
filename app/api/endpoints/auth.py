# from datetime import datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status

# from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm  # OAuth2PasswordBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.deps import AccessTokenBearer, get_current_user  # RefreshTokenBearer
from app.core.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.redis import add_jti_to_blocklist
from app.core.security import TokenData, create_access_token, verify_password
from app.crud.users import UserCRUD
from app.db.session import get_session
from app.schemas.users import PublicUserCreate, TokenRead, UserRead

auth_crud = UserCRUD()
auth_router = APIRouter(tags=["auth"])


async def send_email(to_email: str, subject: str, body: str) -> None:
    # Placeholder function for sending email
    # In production, integrate with an email service provider
    print(f"Sending email to {to_email} with subject '{subject}'")
    print("Email body:")
    print(body)


@auth_router.post(
    "/register", response_model=UserRead, status_code=status.HTTP_201_CREATED
)
async def register_user(
    user_create: PublicUserCreate,
    backend_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
) -> UserRead:
    email = user_create.email
    username = user_create.username
    if not email or not username:
        raise ValidationException(
            message="Email and username are required.",
            details={"field": "email/username"},
        )
    user_exists = await auth_crud.user_exists(session, username, email)
    if user_exists:
        raise ConflictException(
            message="User with given email or username already exists.",
            details={"field": "email/username"},
        )

    new_user = await auth_crud.create_user(session, user_create)

    # send activation email
    activation_link = f"{settings.SERVER_HOST}{settings.API_V1_STR}/auth/activate?token={new_user.activation_token}"
    email_body = f"""
    <h1>Welcome to {settings.APP_NAME}!</h1>
    <p>Thank you for registering. Please click the link below to activate your account:</p>
    <a href="{activation_link}">Activate Account</a>
    <p>If you did not register for this account, please ignore this email.</p>
    <p>Best regards,<br/>{settings.APP_NAME} Team</p>
    """

    backend_tasks.add_task(
        send_email,
        to_email=new_user.email,
        subject=f"{settings.APP_NAME} Activate your account",
        body=email_body,
    )

    user_read = cast(UserRead, UserRead.model_validate(new_user, from_attributes=True))

    return user_read


@auth_router.post("/login", response_model=TokenRead)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],  # noqa: B008
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
) -> TokenRead:
    user = await auth_crud.get_user_for_auth(session, form_data.username)
    if not user:
        raise ResourceNotFoundException(
            resource_id=form_data.username,
            resource_type="User",
        )
    if not verify_password(form_data.password, user.password_hash):
        raise ValidationException(
            message="Incorrect password.",
            details={"field": "password"},
        )

    if not user.is_active:
        raise ValidationException(
            message="User account is inactive/deactivated.",
        )

    if not user.is_verified:
        raise ValidationException(
            message="Plase verify your email first.",
        )

    access_token = create_access_token(
        user_data={
            "username": user.username,
            "email": user.email,
            "uid": str(user.uid),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        }
    )

    refresh_token = create_access_token(
        user_data={
            "username": user.username,
            "email": user.email,
            "uid": str(user.uid),
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
        },
        refresh=True,
    )
    return TokenRead(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@auth_router.get("/activate")
async def activate_account(
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
    token: str = Query(...),  # noqa: B008
) -> JSONResponse:
    user = await auth_crud.get_by_activation_token(session, token)
    if not user:
        raise ValidationException(
            message="Invalid activation token.",
            details={"field": "token"},
        )
    if user.is_verified:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Account already activated."},
        )
    user.is_verified = True
    await auth_crud.update_user(session, str(user.uid), user)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Account activated successfully."},
    )


@auth_router.post("/logout")
async def logout(
    current_user: Annotated[UserRead, Depends(get_current_user)],  # noqa: B008
    token_data: Annotated[TokenData, Depends(AccessTokenBearer())],  # noqa: B008
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
) -> JSONResponse:
    await add_jti_to_blocklist(token_data["jti"])
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Successfully logged out."},
    )
