import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StreamBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    is_private: bool = False


class StreamCreate(StreamBase):
    pass


class StreamUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[str] = None
    is_private: Optional[bool] = None
    thumbnail_url: Optional[str] = None


class StreamResponse(StreamBase):
    sid: uuid.UUID
    user_id: uuid.UUID
    stream_key: str
    rtmp_url: Optional[str]
    hls_url: Optional[str]
    is_live: bool
    current_viewers: int
    total_views: int
    peak_viewers: int
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StreamPublicResponse(BaseModel):
    """Public stream info (without stream key)"""

    sid: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str]
    category: Optional[str]
    thumbnail_url: Optional[str]
    hls_url: Optional[str]
    is_live: bool
    current_viewers: int
    total_views: int
    started_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StreamStartRequest(BaseModel):
    sid: uuid.UUID


class StreamStopRequest(BaseModel):
    sid: uuid.UUID
