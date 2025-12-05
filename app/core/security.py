import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, TypedDict

import jwt
from jwt import ExpiredSignatureError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
logger = logging.getLogger(__name__)


class TokenData(TypedDict):
    user: Dict[str, Any]
    exp: int
    jti: str
    refresh: bool


def get_password_hash(password: str) -> str:
    return str(pwd_context.hash(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bool(pwd_context.verify(plain_password, hashed_password))


class JWTHandler:
    @staticmethod
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

        token = jwt.encode(
            payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
        )
        return str(token)

    @staticmethod
    def decode_token(token: str) -> TokenData | None:
        try:
            token_data = jwt.decode(
                jwt=token,
                key=settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                leeway=10,
            )
            return TokenData(
                user=token_data["user"],
                exp=token_data["exp"],
                jti=token_data["jti"],
                refresh=token_data["refresh"],
            )
        except ExpiredSignatureError:
            # logging.warning("Token expired")
            return None
        except jwt.PyJWTError:
            # logging.exception(e)
            return None


def generate_token() -> str:
    return secrets.token_urlsafe(32)
