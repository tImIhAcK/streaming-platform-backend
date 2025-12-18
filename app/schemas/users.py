import re
import uuid
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.enums.roles import UserRole


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    first_name: Optional[str] = Field(..., min_length=1, max_length=50)
    last_name: Optional[str] = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)

    role: UserRole = UserRole.VIEWER

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        Validate password meets security requirements.

        Requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")

        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/`~]', v):
            raise ValueError("Password must contain at least one special character")

        return v

    @field_validator("username")
    @classmethod
    def validate_username_format(cls, v: str) -> str:
        """
        Validate username format to prevent XSS and injection attacks.
        Only allows alphanumeric characters, hyphens, and underscores.
        """
        v = v.strip()

        if not v or v.isspace():
            raise ValueError("Username cannot be empty or whitespace only")

        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, hyphens, and underscores"
            )

        # Check for common XSS patterns
        xss_patterns = ["<script", "javascript:", "onerror=", "onload=", "<img"]
        if any(pattern in v.lower() for pattern in xss_patterns):
            raise ValueError("Invalid characters in username")

        return v

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_fields(cls, v: str) -> str:
        """
        Validate name fields.
        Trim whitespace and ensure not empty.
        """
        v = v.strip()

        if not v or v.isspace():
            raise ValueError("Name cannot be empty or whitespace only")

        # Allow letters, spaces, hyphens, and apostrophes for names
        if not re.match(r"^[a-zA-Z\s\-']+$", v):
            raise ValueError("Name contains invalid characters")

        return v

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: EmailStr) -> EmailStr:
        """
        Additional email validation.
        EmailStr already validates format, this adds extra checks.
        """
        # Convert to lowercase for consistency
        email_str = str(v).lower().strip()

        # Basic XSS prevention
        if "<" in email_str or ">" in email_str or "script" in email_str.lower():
            raise ValueError("Invalid email format")

        return email_str


class PublicUserCreate(UserCreate):
    role: Literal[UserRole.VIEWER, UserRole.STREAMER] = UserRole.VIEWER


class AdminUserCreate(UserCreate):
    role: UserRole = UserRole.ADMIN


class UserRead(BaseModel):
    """Read User data"""

    uid: uuid.UUID
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_verified: bool
    role: UserRole


class UserReadWithToken(UserRead):
    activation_token: Optional[str] = None


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(..., min_length=1, max_length=50)
    last_name: Optional[str] = Field(..., min_length=1, max_length=50)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    role: Optional[UserRole] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def validate_name_fields(cls, v: str) -> str:
        """
        Validate name fields.
        Trim whitespace and ensure not empty.
        """
        v = v.strip()

        if not v or v.isspace():
            raise ValueError("Name cannot be empty or whitespace only")

        # Allow letters, spaces, hyphens, and apostrophes for names
        if not re.match(r"^[a-zA-Z\s\-']+$", v):
            raise ValueError("Name contains invalid characters")

        return v


class TokenRead(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class PasswordChange(BaseModel):
    """ """

    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Same password validation as registration."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")

        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/`~]', v):
            raise ValueError("Password must contain at least one special character")

        return v


class PasswordResetRequest(BaseModel):
    """ """

    email: EmailStr

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: EmailStr) -> EmailStr:
        """
        Additional email validation.
        EmailStr already validates format, this adds extra checks.
        """
        # Convert to lowercase for consistency
        email_str = str(v).lower().strip()

        # Basic XSS prevention
        if "<" in email_str or ">" in email_str or "script" in email_str.lower():
            raise ValueError("Invalid email format")

        return email_str


class PasswordReset(BaseModel):
    """ """

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Same password validation as registration."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")

        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")

        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")

        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/`~]', v):
            raise ValueError("Password must contain at least one special character")

        return v
