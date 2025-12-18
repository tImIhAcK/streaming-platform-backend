from datetime import datetime, timedelta, timezone
from typing import Annotated, cast

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

# from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.deps import (  # RefreshTokenBearer
    AccessTokenBearer,
    get_current_active_user,
)
from app.core.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.redis import add_jti_to_blocklist
from app.core.redis_rate_limiter import redis_rate_limit
from app.core.security import (
    JWTHandler,
    TokenData,
    generate_token,
    get_password_hash,
    verify_password,
)
from app.crud.users import UserCRUD
from app.db.session import get_session
from app.models.users import User
from app.schemas.users import (
    PasswordChange,
    PasswordReset,
    PasswordResetRequest,
    PublicUserCreate,
    TokenRead,
    UserRead,
)
from app.utils.helper import get_user_identifier

auth_crud = UserCRUD()
auth_router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def send_email(to_email: str, subject: str, body: str) -> None:
    # Placeholder function for sending email
    # In production, integrate with an email service provider
    print(f"Sending email to {to_email} with subject '{subject}'")
    print("Email body:")
    print(body)


# Strict rate limit for registration: 3 requests per 5 minutes
@auth_router.post(
    "/register", response_model=UserRead, status_code=status.HTTP_201_CREATED
)
@redis_rate_limit(capacity=3, refill_rate=0.01, prefix="auth_register:")
async def register_user(
    request: Request,
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


# Strict rate limit for login: 5 attempts per minute
@auth_router.post("/login", response_model=TokenRead)
@redis_rate_limit(capacity=5, refill_rate=0.083, prefix="auth_login:")
async def login(
    request: Request,
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
            message="Incorrect username or password.",
            details={"field": "credentials"},
        )

    if not user.is_active:
        raise ValidationException(
            message="User account is inactive/deactivated.",
        )

    if not user.is_verified:
        raise ValidationException(
            message="Plase verify your email first.",
        )

    access_token = JWTHandler.create_access_token(
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

    refresh_token = JWTHandler.create_access_token(
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


# Lenient rate limit for activation: 10 per minute
@redis_rate_limit(capacity=10, refill_rate=0.167, prefix="auth_activate:")
@auth_router.get("/activate")
async def activate_account(
    request: Request,
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


# Lenient rate limit for logout: 10 per minute
@auth_router.post("/logout")
@redis_rate_limit(
    capacity=10,
    refill_rate=0.167,
    prefix="auth_logout:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def logout(
    request: Request,
    current_user: Annotated[UserRead, Depends(get_current_active_user)],  # noqa: B008
    token_data: Annotated[TokenData, Depends(AccessTokenBearer())],  # noqa: B008
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
) -> JSONResponse:
    await add_jti_to_blocklist(token_data["jti"])
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Successfully logged out."},
    )


# Moderate rate limit for password reset: 3 per 15 minutes
@auth_router.post("/forgot-password")
@redis_rate_limit(capacity=3, refill_rate=0.0033, prefix="auth_forgot:")
async def forgot_password(
    request: Request,
    password_reset_request: PasswordResetRequest,
    backend_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
) -> JSONResponse:
    user = await auth_crud.get_by_email(session, password_reset_request.email)
    if not user:
        raise ResourceNotFoundException(
            resource_id=password_reset_request.email,
            resource_type="User",
        )

    reset_token = generate_token()
    user.reset_token = reset_token
    user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    session.add(user)
    await session.commit()

    reset_link = f"{settings.SERVER_HOST}{settings.API_V1_STR}/auth/reset-password?token={reset_token}"
    email_body = f"""
    <h1>Password Reset Request</h1>
    <p>To reset your password, please click the link below:</p>
    <a href="{reset_link}">Reset Password</a>
    <p>This link will expire in 1 hour.</p>
    <p>If you did not request a password reset, please ignore this email.</p>
    <p>Best regards,<br/>{settings.APP_NAME} Team</p>
    """

    backend_tasks.add_task(
        send_email,
        to_email=user.email,
        subject=f"{settings.APP_NAME} Password Reset Request",
        body=email_body,
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Password reset email sent."},
    )


# Standard rate limit for password reset: 5 per minute
@auth_router.post("/reset-password")
@redis_rate_limit(capacity=5, refill_rate=0.083, prefix="auth_reset:")
async def reset_password(
    request: Request,
    password_reset: PasswordReset,
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
) -> JSONResponse:

    user = await auth_crud.get_by_reset_token(session, password_reset.token)
    if not user or user.reset_token_expires_at < datetime.now(timezone.utc):
        raise ValidationException(
            message="Invalid or expired reset token", details={"field": "token"}
        )
    user.password_hash = get_password_hash(password_reset.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    session.add(user)
    await session.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Password has been reset successfully."},
    )


# Standard rate limit for password change: 5 per minute
@auth_router.post("/change-password")
@redis_rate_limit(
    capacity=5,
    refill_rate=0.083,
    prefix="auth_change:",
    get_identifier=lambda req: get_user_identifier(req),
)
async def change_password(
    request: Request,
    password_change: PasswordChange,
    current_user: Annotated[User, Depends(get_current_active_user)],  # noqa: B008
    session: Annotated[AsyncSession, Depends(get_session)],  # noqa: B008
) -> JSONResponse:

    if not verify_password(password_change.old_password, current_user.password_hash):
        raise ValidationException(
            message="Incorrect old password.",
            details={"field": "current_password"},
        )

    current_user.password_hash = get_password_hash(password_change.new_password)
    session.add(current_user)
    await session.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": "Password has been changed successfully."},
    )
