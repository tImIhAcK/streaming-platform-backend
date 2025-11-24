from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    VIEWER = "viewer"
    STREAMER = "streamer"
    MODERATOR = "moderator"


class PublicUserRole(str, Enum):
    VIEWER = "viewer"
    STREAMER = "streamer"
