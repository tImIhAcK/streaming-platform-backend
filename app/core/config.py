from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Any, Union
import secrets
import json


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
    FRONTEND_HOST: Union[str, list[str]]
    BACKEND_CORS_ORIGINS: Union[str, list[str]]

    DATABASE_URL: str

    SUPERUSER_USERNAME: str
    SUPERUSER_PASSWORD: str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    REDIS_URL: str

    LOG_LEVEL: str
    ENVIRONMENT: str = "development"

    @field_validator("FRONTEND_HOST", "BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    raise ValueError(f"Invalid JSON array: {v}")
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, list):
            return v
        raise ValueError(f"Unsupported type: {type(v)}")

    @property
    def all_cors_origins(self) -> list[str]:
        return list({
            origin.rstrip("/")
            for origin in self.FRONTEND_HOST + self.BACKEND_CORS_ORIGINS
        })
    
settings = Settings()
