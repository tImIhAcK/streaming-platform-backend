import logging
from typing import Any, Dict, Optional

from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppException(Exception):
    """
    Base custom application exception.
    All application-specific exceptions should inherit from this.
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        log_error: bool = True,
    ):
        """
        Initialize AppException

        Args:
            message: Human-readable error message
            status_code: HTTP status code
            error_code: Machine-readable error code (e.g., "INVALID_FILE_FORMAT")
            details: Additional error details/context
            log_error: Whether to log this error
        """
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or "INTERNAL_ERROR"
        self.details = details or {}
        self.log_error = log_error

        super().__init__(self.message)


class ValidationException(AppException):
    """Raised when data validation fails"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code="VALIDATION_ERROR",
            details=details,
        )


class ResourceNotFoundException(AppException):
    """Raised when a requested resource is not found"""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
    ):
        super().__init__(
            message=f"{resource_type} with id '{resource_id}' not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="RESOURCE_NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": resource_id},
            log_error=False,  # Don't log 404s as errors
        )


class UnauthorizedException(AppException):
    """Raised when user is not authenticated"""

    def __init__(self, message: str = "Not authenticated"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            log_error=False,
        )


class ForbiddenException(AppException):
    """Raised when user doesn't have permission"""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            log_error=False,
        )


class ConflictException(AppException):
    """Raised when resource already exists or conflicts"""

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
            details=details,
        )


class InvalidFileException(AppException):
    """Raised when uploaded file is invalid"""

    def __init__(
        self,
        message: str,
        allowed_types: Optional[list[str]] = None,
        max_size: Optional[int] = None,
    ):
        details: Dict[str, Any] = {}
        if allowed_types:
            details["allowed_types"] = allowed_types
        if max_size:
            details["max_size_bytes"] = max_size

        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_FILE",
            details=details,
        )


class ProcessingException(AppException):
    """Raised when background processing fails"""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        message: str,
    ):
        super().__init__(
            message=f"Failed to process {resource_type}: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="PROCESSING_ERROR",
            details={
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )


class DatabaseException(AppException):
    """Raised when database operation fails"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DATABASE_ERROR",
            details=details,
        )


class ExternalServiceException(AppException):
    """Raised when external service call fails"""

    def __init__(
        self,
        service_name: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=f"{service_name} error: {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={
                "service": service_name,
                **(details or {}),
            },
        )


class RateLimitException(AppException):
    """Raised when rate limit is exceeded"""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after} if retry_after else {},
            log_error=False,
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Handle AppException and return standardized JSON response.

    Args:
        request: FastAPI request object
        exc: AppException instance

    Returns:
        JSONResponse with error details
    """

    # Log error if flagged
    if exc.log_error:
        logger.error(
            f"Application Error [{exc.error_code}] - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
                "details": exc.details,
            },
            exc_info=True,
        )
    else:
        # Log at debug level for non-error cases (like 404s)
        logger.debug(
            f"Application Error [{exc.error_code}] - {exc.message}",
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
                "method": request.method,
            },
        )

    # Build response
    error_response = {
        "error": {
            "code": exc.error_code,
            "message": exc.message,
            "status": exc.status_code,
        }
    }

    # Add details if present
    if exc.details:
        error_response["error"]["details"] = exc.details

    # Add request context
    error_response["error"]["path"] = request.url.path
    error_response["error"]["method"] = request.method

    return JSONResponse(
        status_code=exc.status_code,
        content=error_response,
    )
