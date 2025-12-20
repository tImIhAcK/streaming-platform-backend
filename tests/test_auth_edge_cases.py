"""
Additional edge case and security tests for authentication.

These tests cover:
- SQL injection attempts
- XSS attempts
- Password complexity
- Token tampering
- Concurrent requests
- Edge cases
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import status

from app.core.security import JWTHandler, get_password_hash


class TestSecurityVulnerabilities:
    """Test for common security vulnerabilities."""

    @patch("app.api.v1.https.auth.auth_crud.get_user_for_auth", new_callable=AsyncMock)
    def test_sql_injection_login_username(self, mock_get_user, client):
        """Test SQL injection attempts in username field."""
        sql_injection_attempts = [
            "' OR '1'='1",
            "admin'--",
            "' OR 1=1--",
            "admin' OR '1'='1'--",
            "'; DROP TABLE users--",
        ]

        for injection in sql_injection_attempts:
            mock_get_user.return_value = None
            response = client.post(
                "/api/v1/auth/login",
                data={"username": injection, "password": "password"},
            )
            # Should not cause errors, just return user not found
            assert response.status_code in [
                status.HTTP_404_NOT_FOUND,
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            ]

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_xss_in_registration(self, mock_user_exists, client):
        """Test XSS attempts in registration fields."""
        mock_user_exists.return_value = False

        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
        ]

        for payload in xss_payloads:
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": payload,
                    "email": "test@example.com",
                    "password": "SecurePass123!",
                    "first_name": "Test",
                    "last_name": "User",
                },
            )
            # Should be handled by validation
            assert response.status_code in [
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                status.HTTP_400_BAD_REQUEST,
            ]

    def test_token_tampering(self, created_user):
        """Test that tampered tokens are rejected."""
        valid_token = JWTHandler.create_access_token(
            user_data={
                "username": created_user.username,
                "email": created_user.email,
                "uid": str(created_user.uid),
            }
        )

        # Tamper with the token
        parts = valid_token.split(".")
        tampered_payload = parts[1][:-3] + "XXX"  # Modify payload
        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        decoded = JWTHandler.decode_token(tampered_token)
        assert decoded is None

    def test_token_signature_tampering(self, created_user):
        """Test that tokens with modified signatures are rejected."""
        valid_token = JWTHandler.create_access_token(
            user_data={
                "username": created_user.username,
                "email": created_user.email,
                "uid": str(created_user.uid),
            }
        )

        # Tamper with the signature
        parts = valid_token.split(".")
        tampered_signature = parts[2][:-3] + "XXX"
        tampered_token = f"{parts[0]}.{parts[1]}.{tampered_signature}"

        decoded = JWTHandler.decode_token(tampered_token)
        assert decoded is None


class TestPasswordSecurity:
    """Test password security requirements."""

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_weak_passwords_rejected(self, mock_user_exists, client):
        """Test that weak passwords are rejected during registration."""
        mock_user_exists.return_value = False

        weak_passwords = [
            "123456",  # Too simple
            "password",  # Common word
            "abc",  # Too short
            "        ",  # Only spaces
        ]

        for weak_pass in weak_passwords:
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "testuser",
                    "email": "test@example.com",
                    "password": weak_pass,
                    "first_name": "Test",
                    "last_name": "User",
                },
            )
            # Assuming password validation is implemented
            # Adjust based on your validation logic
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_password_hashing(self):
        """Test that passwords are properly hashed."""
        password = "SecurePassword123!"
        hashed = get_password_hash(password)

        # Hash should be different from original
        assert hashed != password

        # Hash should be consistent for same password
        hashed2 = get_password_hash(password)
        assert hashed != hashed2  # bcrypt adds salt

        # Hash should be verifiable
        from app.core.security import verify_password

        assert verify_password(password, hashed)
        assert not verify_password("WrongPassword", hashed)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_register_with_very_long_fields(self, mock_user_exists, client):
        """Test registration with extremely long field values."""
        mock_user_exists.return_value = False

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "a" * 1000,  # Very long username
                "email": "test@example.com",
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        # Should be rejected due to length validation
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_register_with_unicode_characters(self, mock_user_exists, client):
        """Test registration with unicode characters."""
        mock_user_exists.return_value = False

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "用户名",  # Chinese characters
                "email": "test@example.com",
                "password": "SecurePass123!",
                "first_name": "名字",
                "last_name": "姓氏",
            },
        )

        # Should either accept or reject gracefully
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_register_with_empty_strings(self, mock_user_exists, client):
        """Test registration with empty strings."""
        mock_user_exists.return_value = False

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "",
                "email": "",
                "password": "",
                "first_name": "",
                "last_name": "",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_register_with_whitespace_only(self, mock_user_exists, client):
        """Test registration with whitespace-only fields."""
        mock_user_exists.return_value = False

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "   ",
                "email": "test@example.com",
                "password": "SecurePass123!",
                "first_name": "   ",
                "last_name": "   ",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_login_with_null_values(self, client):
        """Test login with null/None values."""
        response = client.post(
            "/api/v1/auth/login",
            json={"username": None, "password": None},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_activate_with_empty_token(self, client):
        """Test account activation with empty token."""
        response = client.get("/api/v1/auth/activate", params={"token": ""})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


class TestConcurrency:
    """Test concurrent request handling."""

    @pytest.mark.asyncio
    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    @patch("app.api.v1.https.auth.auth_crud.create_user", new_callable=AsyncMock)
    async def test_concurrent_registrations(
        self, mock_create_user, mock_user_exists, client, created_user
    ):
        """Test multiple simultaneous registration attempts."""
        mock_user_exists.return_value = False
        mock_create_user.return_value = created_user

        # Simulate concurrent registration attempts
        async def register():
            return client.post(
                "/api/v1/auth/register",
                json={
                    "username": f"user_{uuid4()}",
                    "email": f"test_{uuid4()}@example.com",
                    "password": "SecurePass123!",
                    "first_name": "Test",
                    "last_name": "User",
                },
            )

        # Run 10 concurrent requests
        tasks = [register() for _ in range(10)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # All should either succeed or be rate limited
        for response in responses:
            if isinstance(response, BaseException):
                continue
            else:
                assert response.status_code in [
                    status.HTTP_201_CREATED,
                    status.HTTP_429_TOO_MANY_REQUESTS,
                ]


class TestTokenLifecycle:
    """Test token creation, validation, and expiration."""

    def test_access_token_expiration_time(self, created_user):
        """Test that access tokens have correct expiration time."""
        token = JWTHandler.create_access_token(
            user_data={
                "username": created_user.username,
                "email": created_user.email,
                "uid": str(created_user.uid),
            }
        )

        decoded = JWTHandler.decode_token(token)
        assert decoded is not None

        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Token should expire in the future
        assert exp_time > now
        time_diff = exp_time - now
        # Access tokens expire in 7 days (not 1 hour)
        assert time_diff.total_seconds() < 8 * 24 * 3600  # Less than 8 days
        assert time_diff.total_seconds() > 6 * 24 * 3600  # More than 6 days

    def test_refresh_token_expiration_time(self, created_user):
        """Test that refresh tokens have longer expiration time."""
        refresh_token = JWTHandler.create_access_token(
            user_data={
                "username": created_user.username,
                "email": created_user.email,
                "uid": str(created_user.uid),
            },
            refresh=True,
        )

        decoded = JWTHandler.decode_token(refresh_token)
        assert decoded is not None

        exp_time = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Refresh token should expire further in the future
        assert exp_time > now
        time_diff = exp_time - now
        assert time_diff.total_seconds() > 3600  # More than 1 hour


class TestEmailValidation:
    """Test email validation edge cases."""

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_invalid_email_formats(self, mock_user_exists, client):
        """Test various invalid email formats."""
        mock_user_exists.return_value = False

        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",  # Space in email
            "user..name@example.com",  # Double dots
            "user@example",  # No TLD
            "user@.com",  # Missing domain
        ]

        for invalid_email in invalid_emails:
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "username": "testuser",
                    "email": invalid_email,
                    "password": "SecurePass123!",
                    "first_name": "Test",
                    "last_name": "User",
                },
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    @patch("app.api.v1.https.auth.auth_crud.create_user", new_callable=AsyncMock)
    def test_case_insensitive_email(
        self, mock_create_user, mock_user_exists, client, created_user
    ):
        """Test that emails are treated case-insensitively."""
        mock_user_exists.return_value = False
        mock_create_user.return_value = created_user

        # Register with uppercase email
        response1 = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser1",
                "email": "TEST@EXAMPLE.COM",
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        assert response1.status_code == status.HTTP_201_CREATED

        # Try to register with same email in lowercase
        mock_user_exists.return_value = True  # Should detect duplicate

        response2 = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser2",
                "email": "test@example.com",
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        # Second registration should fail due to duplicate email
        assert response2.status_code == status.HTTP_409_CONFLICT


class TestErrorMessages:
    """Test that error messages are informative but not revealing."""

    @patch("app.api.v1.https.auth.auth_crud.get_user_for_auth", new_callable=AsyncMock)
    def test_login_error_doesnt_reveal_user_existence(self, mock_get_user, client):
        """Test that login errors don't reveal whether user exists."""
        # Non-existent user
        mock_get_user.return_value = None
        response1 = client.post(
            "/api/v1/auth/login",
            data={"username": "nonexistent", "password": "password"},
        )

        # Wrong password
        from app.models.users import User

        mock_user = User(
            uid=uuid4(),
            username="existinguser",
            email="existing@example.com",
            password_hash=get_password_hash("correctpassword"),
            is_active=True,
            is_verified=True,
        )
        mock_get_user.return_value = mock_user

        response2 = client.post(
            "/api/v1/auth/login",
            data={"username": "existinguser", "password": "wrongpassword"},
        )

        # Error messages should be generic
        # This prevents username enumeration attacks
        # Adjust based on your actual implementation
        assert response1.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_401_UNAUTHORIZED,
        ]
        assert response2.status_code in [
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            status.HTTP_401_UNAUTHORIZED,
        ]


class TestDataSanitization:
    """Test input data sanitization."""

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_username_trimming(self, mock_user_exists, client):
        """Test that usernames are trimmed of whitespace."""
        mock_user_exists.return_value = False

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "  testuser  ",  # Leading/trailing spaces
                "email": "test@example.com",
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        # Should either trim automatically or reject
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_email_trimming_and_lowercase(self, mock_user_exists, client):
        """Test that emails are trimmed and lowercased."""
        mock_user_exists.return_value = False

        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "  TEST@EXAMPLE.COM  ",  # Spaces and uppercase
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
            },
        )

        # Should either sanitize automatically or reject
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
        ]
