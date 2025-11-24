from app.core.deps import RoleChecker

admin_role_checker = RoleChecker(allowed_roles=["admin"])
streamer_role_checker = RoleChecker(allowed_roles=["streamer"])
viewer_role_checker = RoleChecker(allowed_roles=["viewer"])
moderator_role_checker = RoleChecker(allowed_roles=["moderator"])
