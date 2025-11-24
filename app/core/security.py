import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, TypedDict, cast

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
logger = logging.getLogger(__name__)


class TokenData(TypedDict):
    user: dict[str, Any]
    exp: int
    jti: str
    refresh: bool


def get_password_hash(password: str) -> str:
    return str(pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bool(pwd_context.verify(plain_password, hashed_password))


def create_access_token(
    user_data: Dict[str, Any],
    expires_delta: timedelta | None = None,
    refresh: bool = False,
) -> str:
    payload: Dict[str, Any] = {
        "user": user_data,
        "exp": int(
            (
                datetime.now(timezone.utc)
                + (
                    expires_delta
                    if expires_delta is not None
                    else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                )
            ).timestamp()
        ),
        "jti": str(uuid.uuid4()),
        "refresh": refresh,
    }

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return str(token)


def decode_token(token: str) -> TokenData:
    try:
        token_data = jwt.decode(
            jwt=token,
            key=settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            leeway=10,
        )
        return cast(TokenData, token_data)
    except InvalidTokenError as e:
        if isinstance(e, ExpiredSignatureError):
            raise ExpiredSignatureError("Token has expired")
        raise InvalidTokenError("Invalid token")


def generate_token() -> str:
    return secrets.token_urlsafe(32)
