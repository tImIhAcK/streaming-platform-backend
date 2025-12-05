from enum import Enum


class Permission(str, Enum):
    # User Management
    CREATE_USER = "create_user"
    READ_USER = "read_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    LIST_USERS = "list_users"
    ASSIGN_ROLES = "assign_roles"

    # Stream Management
    CREATE_STREAM = "create_stream"
    READ_STREAM = "read_stream"
    UPDATE_STREAM = "update_stream"
    DELETE_STREAM = "delete_stream"
    LIST_STREAMS = "list_streams"
    START_STREAM = "start_stream"
    STOP_STREAM = "stop_stream"
    CONFIGURE_STREAM = "configure_stream"

    # Stream Interaction
    VIEW_STREAM = "view_stream"
    COMMENT_ON_STREAM = "comment_on_stream"
    REACT_TO_STREAM = "react_to_stream"

    # Moderation
    MODERATE_CHAT = "moderate_chat"
    BAN_USER = "ban_user"
    UNBAN_USER = "unban_user"
    TIMEOUT_USER = "timeout_user"
    DELETE_COMMENT = "delete_comment"
    PIN_COMMENT = "pin_comment"
    SLOW_MODE = "slow_mode"

    # Moderator Management
    ADD_MODERATOR = "add_moderator"
    REMOVE_MODERATOR = "remove_moderator"
    LIST_MODERATORS = "list_moderators"

    # Analytics & Reports
    VIEW_ANALYTICS = "view_analytics"
    VIEW_STREAM_STATS = "view_stream_stats"
    VIEW_USER_REPORTS = "view_user_reports"
    EXPORT_DATA = "export_data"

    # System & Settings
    MANAGE_SETTINGS = "manage_settings"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_PERMISSIONS = "manage_permissions"

    # Notifications
    SEND_NOTIFICATIONS = "send_notifications"
    MANAGE_ALERTS = "manage_alerts"
