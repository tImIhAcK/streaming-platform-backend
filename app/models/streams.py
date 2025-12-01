import secrets
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import sqlalchemy.dialects.postgresql as pg
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.users import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StreamBase(SQLModel):
    # Stream Information
    title: str = Field(
        min_length=3, max_length=255, index=True, nullable=False, unique=False
    )
    description: Optional[str] = Field(
        sa_column=Column(pg.TEXT, nullable=True),
    )
    category: Optional[str] = Field(
        sa_column=Column(pg.VARCHAR, nullable=True),
        default=None,
    )
    thumbnail_url: Optional[str] = Field(default=None, nullable=True)

    # Stream credentials
    stream_key: str = Field(max_length=100, unique=True, nullable=False, index=True)
    rtmp_url: Optional[str] = Field(max_length=500, nullable=True)
    hls_url: Optional[str] = Field(max_length=500, nullable=True)

    # Stream Status
    is_live: bool = Field(default=False)
    is_private: bool = Field(default=False)

    # Analytics
    current_viewers: int = Field(default=0)
    total_views: int = Field(default=0)
    peak_viewers: int = Field(default=0)

    # Timestamps
    started_at: Optional[datetime] = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True)
    )
    ended_at: Optional[datetime] = Field(
        default=None, sa_column=Column(pg.TIMESTAMP(timezone=True), nullable=True)
    )
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


class Stream(StreamBase, table=True):
    __tablename__ = "streams"

    sid: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4, primary_key=True, nullable=False, index=True
    )
    user_id: uuid.UUID = Field(foreign_key="users.uid", nullable=False, index=True)

    user: Optional["User"] = Relationship(back_populates="streams")

    @staticmethod
    def generate_stream_key() -> str:
        return secrets.token_urlsafe(32)
