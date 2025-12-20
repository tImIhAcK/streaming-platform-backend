import json
import secrets
from functools import lru_cache
from typing import Any, List, Optional, Union

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# from dotenv import load_dotenv

# load_dotenv(dotenv_path='.env')

# ENV = os.environ.get("ENVIRONMENT", "development").strip("'\"").lower()
# ENV_FILE = ".env.prod" if ENV == "production" else ".env.local"
# print(ENV_FILE)


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

    DATABASE_URL: str = ""
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    ENVIRONMENT: str

    SUPERUSER_USERNAME: str
    SUPERUSER_PASSWORD: str
    SUPERUSER_EMAIL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str
    REDIS_URL: str
    LOG_LEVEL: str

    RTMP_SERVER_URL: str
    HLS_BASE_URL: str
    RTMP_WEBHOOK_SECRET: Optional[str] = None

    @model_validator(mode="after")
    def assemble_db_url(self) -> "Settings":
        # If DATABASE_URL is not provided or is empty, construct it
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://"
                f"{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/"
                f"{self.POSTGRES_DB}"
            )
        return self

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
