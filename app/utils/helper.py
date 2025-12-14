from fastapi import Request


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return str(forwarded.split(",")[0].strip())

    if request.client is not None:
        return str(request.client.host)

    return "unknown"


def get_user_identifier(request: Request) -> str:
    """Extract user identifier (e.g., from auth token)"""
    # Try to get user from auth header
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return str(auth[7:])  # Use token as identifier

    # Fallback to IP
    return str(get_client_ip(request))


# 8168751375
