import json
import secrets
from typing import Any, List, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_ignore_empty=True,
        case_sensitive=True,
        env_file_encoding="utf-8",
    )

    APP_NAME: str = "Streaming Platform"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    REFRESH_TOKEN_EXPIRY: int = 2
    SERVER_HOST: str = "http://localhost:8000"
    FRONTEND_HOST: Union[str, list[str]] = []
    BACKEND_CORS_ORIGINS: Union[str, list[str]] = []

    DATABASE_URL: str
    SUPERUSER_USERNAME: str
    SUPERUSER_PASSWORD: str
    SUPERUSER_EMAIL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    REDIS_URL: str
    LOG_LEVEL: str
    ENVIRONMENT: str = "development"

    @field_validator("FRONTEND_HOST", "BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> List[str]:
        """Always convert str or list into list[str]"""
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item).strip() for item in v]

        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if not isinstance(parsed, list):
                        raise ValueError("Expected a JSON list")
                    return [str(item).strip() for item in parsed]
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON array: {v}") from e

            # comma separated list
            return [item.strip() for item in v.split(",") if item.strip()]

        raise ValueError(f"Unsupported type: {type(v)}")

    @property
    def all_cors_origins(self) -> List[str]:
        """Combine FRONTEND_HOST + BACKEND_CORS_ORIGINS safely."""
        origins: List[str] = []

        if isinstance(self.FRONTEND_HOST, list):
            origins.extend(self.FRONTEND_HOST)
        else:
            origins.append(self.FRONTEND_HOST)

        if isinstance(self.BACKEND_CORS_ORIGINS, list):
            origins.extend(self.BACKEND_CORS_ORIGINS)
        else:
            origins.append(self.BACKEND_CORS_ORIGINS)

        # normalize duplicates and trailing slashes
        return list({origin.rstrip("/") for origin in origins})

    @property
    def ALLOWED_HOSTS(self) -> list[str]:
        return self.all_cors_origins

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_OAUTH_REDIRECT_URI: str


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
