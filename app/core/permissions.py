from typing import Annotated, Set

from fastapi import Depends

from app.core.deps import get_current_active_user
from app.core.exceptions import ForbiddenException
from app.enums.permissions import Permission
from app.enums.roles import UserRole
from app.models.users import User

# Permission groups
USER_MANAGEMENT = {
    Permission.CREATE_USER,
    Permission.READ_USER,
    Permission.UPDATE_USER,
    Permission.DELETE_USER,
    Permission.LIST_USERS,
    Permission.ASSIGN_ROLES,
}

STREAM_MANAGEMENT = {
    Permission.CREATE_STREAM,
    Permission.READ_STREAM,
    Permission.UPDATE_STREAM,
    Permission.DELETE_STREAM,
    Permission.LIST_STREAMS,
    Permission.START_STREAM,
    Permission.STOP_STREAM,
    Permission.CONFIGURE_STREAM,
}

STREAM_INTERACTION = {
    Permission.VIEW_STREAM,
    Permission.COMMENT_ON_STREAM,
    Permission.REACT_TO_STREAM,
}

MODERATION = {
    Permission.MODERATE_CHAT,
    Permission.BAN_USER,
    Permission.UNBAN_USER,
    Permission.TIMEOUT_USER,
    Permission.DELETE_COMMENT,
    Permission.PIN_COMMENT,
    Permission.SLOW_MODE,
}

MODERATOR_MGMT = {
    Permission.ADD_MODERATOR,
    Permission.REMOVE_MODERATOR,
    Permission.LIST_MODERATORS,
}

ANALYTICS = {
    Permission.VIEW_ANALYTICS,
    Permission.VIEW_STREAM_STATS,
    Permission.VIEW_USER_REPORTS,
    Permission.EXPORT_DATA,
}

SYSTEM_SETTINGS = {
    Permission.MANAGE_SETTINGS,
    Permission.VIEW_AUDIT_LOGS,
    Permission.MANAGE_PERMISSIONS,
}

NOTIFICATIONS = {
    Permission.SEND_NOTIFICATIONS,
    Permission.MANAGE_ALERTS,
}

ROLE_PERMISSIONS = {
    UserRole.ADMIN: {
        *USER_MANAGEMENT,
        *STREAM_MANAGEMENT,
        *STREAM_INTERACTION,
        *MODERATION,
        *MODERATOR_MGMT,
        *ANALYTICS,
        *SYSTEM_SETTINGS,
        *NOTIFICATIONS,
    },
    UserRole.STREAMER: {
        Permission.READ_USER,
        Permission.LIST_USERS,
        *STREAM_MANAGEMENT,
        *STREAM_INTERACTION,
        *MODERATION,
        *MODERATOR_MGMT,
        Permission.VIEW_ANALYTICS,
        Permission.VIEW_STREAM_STATS,
        Permission.EXPORT_DATA,
        *NOTIFICATIONS,
    },
    UserRole.MODERATOR: {
        Permission.READ_USER,
        Permission.LIST_USERS,
        Permission.READ_STREAM,
        Permission.LIST_STREAMS,
        *STREAM_INTERACTION,
        *MODERATION,
        Permission.VIEW_STREAM_STATS,
    },
    UserRole.VIEWER: {
        Permission.READ_USER,
        Permission.READ_STREAM,
        Permission.LIST_STREAMS,
        *STREAM_INTERACTION,
    },
}


class PermissionChecker:
    def __init__(self, permissions: Set[Permission], mode: str = "all") -> None:
        self.permissions = permissions
        self.mode = mode

    def __call__(
        self, current_user: Annotated[User, Depends(get_current_active_user)]
    ) -> User:
        role = UserRole(current_user.role)
        user_permissions = ROLE_PERMISSIONS.get(role, set())

        if self.mode == "all":
            if not self.permissions.issubset(user_permissions):
                missing = self.permissions - user_permissions
                raise ForbiddenException(
                    message=f"Insufficient permissions. Missing: {', '.join(p.value for p in missing)}"
                )

        elif self.mode == "any":
            if not self.permissions.intersection(user_permissions):
                raise ForbiddenException(message="User lacks all required permissions")
        return current_user


def has_permission(user: User, permission: Permission) -> bool:
    role = UserRole(user.role)
    user_permissions = ROLE_PERMISSIONS.get(role, set())
    return permission in user_permissions
