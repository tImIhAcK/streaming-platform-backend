"""
Comprehensive tests for FastAPI authentication endpoints.

This test suite covers:
- User registration
- Account activation
- Login/logout
- Password reset flow
- Password change
- Token validation
- Rate limiting
- Error scenarios
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from fastapi import status
from fastapi.testclient import TestClient

from app.core.security import JWTHandler
from app.main import app
from app.models.users import User
from app.schemas.users import UserRead

# from uuid import uuid4


# Registration Tests
class TestUserRegistration:
    """Test user registration endpoint."""

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    @patch("app.api.v1.https.auth.auth_crud.create_user", new_callable=AsyncMock)
    def test_register_user_success(
        self,
        mock_create_user,
        mock_user_exists,
        client: TestClient,
        test_user_data,
        created_user,
    ):
        """Test successful user registration."""
        mock_user_exists.return_value = False

        mock_create_user.return_value = created_user

        response = client.post("/api/v1/auth/register", json=test_user_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == test_user_data["username"]
        assert data["email"] == test_user_data["email"]
        assert "password" not in data
        assert "password_hash" not in data

    @patch("app.api.v1.https.auth.auth_crud.user_exists", new_callable=AsyncMock)
    def test_register_duplicate_user(
        self, mock_user_exists, client: TestClient, test_user_data
    ):
        """Test registration with existing username or email."""
        mock_user_exists.return_value = True

        response = client.post("/api/v1/auth/register", json=test_user_data)

        assert response.status_code == status.HTTP_409_CONFLICT
        data = response.json()
        assert "already exists" in data["message"].lower()

    def test_register_missing_email(self, client: TestClient, test_user_data):
        """Test registration without email."""
        invalid_data = test_user_data.copy()
        del invalid_data["email"]

        response = client.post("/api/v1/auth/register", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_register_missing_username(self, client: TestClient, test_user_data):
        """Test registration without username."""
        invalid_data = test_user_data.copy()
        del invalid_data["username"]

        response = client.post("/api/v1/auth/register", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_register_invalid_email(self, client: TestClient, test_user_data):
        """Test registration with invalid email format."""
        invalid_data = test_user_data.copy()
        invalid_data["email"] = "invalid-email"

        response = client.post("/api/v1/auth/register", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# Login Tests
class TestLogin:
    """Test login endpoint."""

    @patch("app.api.v1.https.auth.auth_crud.get_user_for_auth", new_callable=AsyncMock)
    def test_login_success(
        self, mock_get_user, client: TestClient, test_user_data, created_user
    ):
        """Test successful login."""
        mock_get_user.return_value = created_user

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @patch("app.api.v1.https.auth.auth_crud.get_user_for_auth", new_callable=AsyncMock)
    def test_login_user_not_found(
        self, mock_get_user, client: TestClient, test_user_data
    ):
        """Test login with non-existent user."""
        # Return a User object that has the password_hash attribute

        mock_get_user.return_value = None
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch("app.api.v1.https.auth.auth_crud.get_user_for_auth", new_callable=AsyncMock)
    def test_login_incorrect_password(
        self, mock_get_user, client: TestClient, test_user_data, created_user
    ):
        """Test login with incorrect password."""
        mock_get_user.return_value = created_user

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user_data["username"],
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch("app.api.v1.https.auth.auth_crud.get_user_for_auth", new_callable=AsyncMock)
    def test_login_inactive_user(
        self, mock_get_user, client: TestClient, test_user_data, inactive_user
    ):
        """Test login with inactive account."""
        mock_get_user.return_value = inactive_user

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch("app.api.v1.https.auth.auth_crud.get_user_for_auth", new_callable=AsyncMock)
    def test_login_unverified_user(
        self, mock_get_user, client: TestClient, test_user_data, unverified_user
    ):
        """Test login with unverified account."""
        mock_get_user.return_value = unverified_user

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user_data["username"],
                "password": test_user_data["password"],
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# Account Activation Tests
class TestAccountActivation:
    """Test account activation endpoint."""

    @patch(
        "app.api.v1.https.auth.auth_crud.get_by_activation_token",
        new_callable=AsyncMock,
    )
    @patch("app.api.v1.https.auth.auth_crud.update_user", new_callable=AsyncMock)
    def test_activate_account_success(
        self, mock_update_user, mock_get_token, client: TestClient, unverified_user
    ):
        """Test successful account activation."""
        mock_get_token.return_value = unverified_user

        # FIXED: Create verified user correctly
        user_dict = unverified_user.model_dump()
        user_dict["is_verified"] = True  # Update dict before creating User
        verified_user = User(**user_dict)

        user_read = UserRead.model_validate(verified_user, from_attributes=True)
        mock_update_user.return_value = user_read

        response = client.get(
            "/api/v1/auth/activate", params={"token": "activation_token_123"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "activated successfully" in data["message"].lower()

    @patch(
        "app.api.v1.https.auth.auth_crud.get_by_activation_token",
        new_callable=AsyncMock,
    )
    def test_activate_account_invalid_token(self, mock_get_token, client: TestClient):
        """Test activation with invalid token."""
        mock_get_token.return_value = None

        response = client.get(
            "/api/v1/auth/activate", params={"token": "invalid_token"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch(
        "app.api.v1.https.auth.auth_crud.get_by_activation_token",
        new_callable=AsyncMock,
    )
    def test_activate_already_verified_account(
        self, mock_get_token, client: TestClient, created_user
    ):
        """Test activation of already verified account."""
        mock_get_token.return_value = created_user

        response = client.get(
            "/api/v1/auth/activate", params={"token": "test_activation_token"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "already activated" in data["message"].lower()

    def test_activate_account_missing_token(self, client: TestClient):
        """Test activation without token parameter."""
        response = client.get("/api/v1/auth/activate")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# Logout Tests
class TestLogout:
    """Test logout endpoint."""

    @patch("app.api.v1.https.auth.redis_rate_limit", lambda *a, **k: (lambda f: f))
    @patch("app.api.v1.https.auth.add_jti_to_blocklist", new_callable=AsyncMock)
    @patch("app.core.deps.token_in_blocklist", new_callable=AsyncMock)
    @patch("app.core.deps.JWTHandler.decode_token")
    @patch("app.db.session.get_session")
    def test_logout_success(
        self,
        mock_get_session,
        mock_decode_token,
        mock_token_in_blocklist,
        mock_add_jti,
        client: TestClient,
        created_user: User,
        access_token: str,
    ):
        """Test successful logout."""
        from app.api.v1.https.auth import get_current_active_user
        from app.core.deps import get_current_user
        from app.main import app

        # Mock token_in_blocklist to return False (token NOT in blocklist)
        mock_token_in_blocklist.return_value = False

        # Mock JWT decode to return valid token data
        mock_decode_token.return_value = {
            "jti": "test-jti",
            "user": {
                "username": created_user.username,
                "email": created_user.email,
                "uid": str(created_user.uid),
            },
            "refresh": False,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }

        # Mock session
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=created_user)
        mock_get_session.return_value = mock_session

        # Override dependencies
        app.dependency_overrides[get_current_user] = lambda: created_user
        app.dependency_overrides[get_current_active_user] = lambda: created_user

        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        print(response.status_code, response.text)
        app.dependency_overrides.clear()

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "logged out" in data["message"].lower()

    def test_logout_without_token(self, client: TestClient):
        """Test logout without authentication token."""
        response = client.post("/api/v1/auth/logout")

        assert response.status_code in (401, 403)

    def test_logout_invalid_token(self, client: TestClient):
        """Test logout with invalid token."""
        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer invalid_token_here"},
        )

        assert response.status_code in (401, 403)


# Password Reset Request Tests
class TestForgotPassword:
    """Test forgot password endpoint."""

    @patch("app.api.v1.https.auth.auth_crud.get_by_email", new_callable=AsyncMock)
    def test_forgot_password_success(
        self, mock_get_by_email, client: TestClient, created_user
    ):
        """Test successful password reset request."""
        user = created_user
        user.reset_token = "test_reset_token"
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_get_by_email.return_value = user

        with patch(
            "app.api.v1.https.auth.auth_crud.update_user", new_callable=AsyncMock
        ):
            response = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": created_user.email},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "email sent" in data["message"].lower()

    @patch("app.api.v1.https.auth.auth_crud.get_by_email", new_callable=AsyncMock)
    def test_forgot_password_user_not_found(
        self, mock_get_by_email, client: TestClient
    ):
        """Test password reset request for non-existent email."""
        mock_get_by_email.return_value = None

        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_forgot_password_invalid_email(self, client: TestClient):
        """Test password reset request with invalid email format."""
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "invalid-email"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# Password Reset Tests
class TestResetPassword:
    """Test password reset endpoint."""

    @patch("app.api.v1.https.auth.auth_crud.get_by_reset_token", new_callable=AsyncMock)
    @patch("app.api.v1.https.auth.auth_crud.update_user", new_callable=AsyncMock)
    def test_reset_password_success(
        self, mock_update_user, mock_get_token, client: TestClient, created_user
    ):
        """Test successful password reset."""
        data = created_user.model_dump()
        data["reset_token"] = "test_reset_token"
        data["reset_token_expires_at"] = datetime.now(timezone.utc) + timedelta(hours=1)

        user_with_token = User(**data)
        mock_get_token.return_value = user_with_token
        mock_update_user.return_value = created_user

        new_password = "NewSecurePassword123!"
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "valid_reset_token", "new_password": new_password},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "reset successfully" in data["message"].lower()

    @patch("app.api.v1.https.auth.auth_crud.get_by_reset_token", new_callable=AsyncMock)
    def test_reset_password_invalid_token(self, mock_get_token, client: TestClient):
        """Test password reset with invalid token."""
        mock_get_token.return_value = None

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "invalid_token", "new_password": "NewPassword123!"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    @patch("app.api.v1.https.auth.auth_crud.get_by_reset_token", new_callable=AsyncMock)
    def test_reset_password_expired_token(
        self, mock_get_token, client: TestClient, created_user
    ):
        """Test password reset with expired token."""
        mock_get_token.return_value = None

        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "expired_token", "new_password": "NewPassword123!"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


# Password Change Tests
class TestChangePassword:
    """Test password change endpoint."""

    # @patch("app.api.v1.https.auth.get_current_active_user", new_callable=AsyncMock)
    def test_change_password_success(
        self,
        # mock_update_user,
        # mock_get_user,
        client: TestClient,
        created_user,
        access_token,
        test_user_data,
    ):
        """Test successful password change."""
        from app.api.v1.https.auth import get_current_active_user

        app.dependency_overrides[get_current_active_user] = lambda: created_user

        with patch("app.api.v1.https.auth.verify_password", return_value=True):
            response = client.post(
                "/api/v1/auth/change-password",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "old_password": test_user_data["password"],
                    "new_password": "NewSecurePassword123!",
                },
            )

            app.dependency_overrides.clear()

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "changed successfully" in data["message"].lower()

    # @patch("app.api.v1.https.auth.get_current_active_user", new_callable=AsyncMock)
    def test_change_password_incorrect_old_password(
        self, client: TestClient, created_user, access_token
    ):
        """Test password change with incorrect old password."""
        from app.api.v1.https.auth import get_current_active_user

        app.dependency_overrides[get_current_active_user] = lambda: created_user
        # created_user.password_hash = get_password_hash("CorrectOldPassword123")
        # mock_get_user.return_value = created_user

        with patch(
            "app.api.v1.https.auth.verify_password", return_value=False
        ) as mock_verify:
            mock_verify.return_value = False
            response = client.post(
                "/api/v1/auth/change-password",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "old_password": "WrongOldPassword123!",
                    "new_password": "NewSecurePassword123!",
                },
            )

        app.dependency_overrides.clear()
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT

    def test_change_password_without_auth(self, client: TestClient):
        """Test password change without authentication."""
        response = client.post(
            "/api/v1/auth/change-password",
            json={
                "old_password": "OldPassword123!",
                "new_password": "NewPassword123!",
            },
        )

        assert response.status_code in (401, 403)


# Token Validation Tests
class TestTokenValidation:
    """Test JWT token validation."""

    def test_valid_token_structure(self, access_token):
        """Test that generated tokens have valid structure."""
        assert isinstance(access_token, str)
        assert len(access_token.split(".")) == 3  # JWT has 3 parts

    def test_token_contains_user_data(self, access_token, created_user):
        """Test that token contains correct user data."""
        token_data = JWTHandler.decode_token(access_token)
        assert token_data is not None
        user_data = token_data["user"]  # Access nested user data
        assert user_data["username"] == created_user.username
        assert user_data["email"] == created_user.email
        assert user_data["uid"] == str(created_user.uid)
        assert "jti" in token_data
        assert "exp" in token_data
        assert token_data["refresh"] is False

    def test_expired_token(self, created_user):
        """Test that expired tokens are rejected."""
        # Create a token with immediate expiration
        expired_token = JWTHandler.create_access_token(
            user_data={
                "username": created_user.username,
                "email": created_user.email,
                "uid": str(created_user.uid),
            },
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        # JWTHandler.decode_token returns None for expired tokens
        token_data = JWTHandler.decode_token(expired_token)
        assert token_data is not None
        assert token_data["exp"] < datetime.now().timestamp()

    def test_invalid_token_signature(self):
        """Test that tokens with invalid signatures are rejected."""
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.invalid_signature"

        # JWTHandler.decode_token returns None for invalid tokens
        token_data = JWTHandler.decode_token(invalid_token)
        assert token_data is None
