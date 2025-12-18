"""
Pytest configuration and fixtures for testing.

This module provides:
- Test database setup with SQLite in-memory
- Test client configuration
- Mock fixtures for external dependencies (Redis, Email)
- User fixtures for testing
- Async/sync test support
"""

import asyncio

# from datetime import datetime, timezone
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.core.security import JWTHandler, get_password_hash
from app.enums.roles import PublicUserRole
from app.main import app
from app.models.users import User

# from app.schemas.users import UserRead

# Test Database Configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ============================================================================
# Event Loop Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop_policy():
    """Set the event loop policy for the test session."""
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session")
def event_loop(event_loop_policy):
    """Create an event loop for the test session."""
    loop = event_loop_policy.new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="function")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create a test database engine with SQLite in-memory.

    This fixture:
    - Creates a new in-memory database for each test
    - Sets up all tables from SQLModel metadata
    - Cleans up after the test completes
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Drop all tables and dispose engine
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create a test database session.

    This fixture provides an async database session for tests that need
    to interact with the database directly.
    """
    async_session_maker = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session


# ============================================================================
# Test Data Fixtures
# ============================================================================


@pytest.fixture
def test_user_data():
    """Provide standard test user data."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "SecurePassword123!",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def created_user(test_user_data):
    """Mock a user object that exists in the database."""
    return User(
        uid=uuid4(),
        username=test_user_data["username"],
        email=test_user_data["email"],
        password_hash=get_password_hash(test_user_data["password"]),
        first_name=test_user_data["first_name"],
        last_name=test_user_data["last_name"],
        role=PublicUserRole.VIEWER,
        is_active=True,
        is_verified=True,
        activation_token="test_activation_token",
    )


@pytest.fixture
def unverified_user(test_user_data):
    """Mock an unverified user."""
    return User(
        uid=uuid4(),
        username=test_user_data["username"],
        email=test_user_data["email"],
        password_hash=get_password_hash(test_user_data["password"]),
        first_name=test_user_data["first_name"],
        last_name=test_user_data["last_name"],
        role=PublicUserRole.VIEWER,
        is_active=True,
        is_verified=False,
        activation_token="activation_token_123",
    )


@pytest.fixture
def inactive_user(test_user_data):
    """Mock an inactive user."""
    return User(
        uid=uuid4(),
        username=test_user_data["username"],
        email=test_user_data["email"],
        password_hash=get_password_hash(test_user_data["password"]),
        first_name=test_user_data["first_name"],
        last_name=test_user_data["last_name"],
        role=PublicUserRole.VIEWER,
        is_active=False,
        is_verified=True,
        activation_token="test_activation_token",
    )


@pytest.fixture
def access_token(created_user):
    """Generate a valid access token for testing."""
    return JWTHandler.create_access_token(
        user_data={
            "username": created_user.username,
            "email": created_user.email,
            "uid": str(created_user.uid),
            "first_name": created_user.first_name,
            "last_name": created_user.last_name,
            "role": created_user.role,
            "is_active": created_user.is_active,
            "is_verified": created_user.is_verified,
        }
    )


# ============================================================================
# FastAPI Client Fixture
# ============================================================================


@pytest.fixture(scope="function")
def client(test_engine: AsyncEngine) -> Generator[TestClient, None, None]:
    """
    Create a test client with mocked dependencies.

    This fixture:
    - Overrides the database session dependency
    - Mocks Redis rate limiting
    - Mocks email sending
    - Mocks authentication dependencies
    - Provides a TestClient for making HTTP requests
    """

    # Create session factory for dependency override
    async_session_maker = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def get_session_override() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            yield session

    # Override dependencies
    from app.db.session import get_session

    app.dependency_overrides[get_session] = get_session_override

    # Create context managers for all mocks
    with (
        patch("app.core.redis_rate_limiter.redis_rate_limit") as mock_rate_limit,
        patch("app.core.redis.token_blocklist") as mock_token_blocklist,
        patch("app.api.v1.https.auth.send_email") as mock_send_email,
        patch(
            "app.core.redis.add_jti_to_blocklist", new_callable=AsyncMock
        ) as mock_blocklist,
        patch(
            "app.core.redis.token_in_blocklist", new_callable=AsyncMock
        ) as mock_token_check,
    ):

        # Configure rate limiter mock (decorator that does nothing)
        mock_rate_limit.return_value = lambda func: func

        # Configure Redis client mock
        mock_redis_instance = MagicMock()
        mock_redis_instance.get = AsyncMock(return_value=None)
        mock_redis_instance.setex = AsyncMock(return_value=True)
        mock_redis_instance.delete = AsyncMock(return_value=True)
        mock_redis_instance.exists = AsyncMock(return_value=False)
        # mock_redis_client.return_value = mock_redis_instance

        # Configure token blocklist mock
        mock_token_blocklist_instance = MagicMock()
        mock_token_blocklist_instance.get = AsyncMock(return_value=None)
        mock_token_blocklist_instance.set = AsyncMock(return_value=True)
        mock_token_blocklist_instance.setex = AsyncMock(return_value=True)
        mock_token_blocklist_instance.delete = AsyncMock(return_value=True)
        mock_token_blocklist_instance.exists = AsyncMock(return_value=False)
        mock_token_blocklist.return_value = mock_token_blocklist_instance

        # Configure email mock
        mock_send_email.return_value = None

        # Configure blocklist function mocks
        mock_blocklist.return_value = None
        mock_token_check.return_value = False  # Token not in blocklist

        async def mock_get_current_active_user():
            # Return a default mock user for tests
            return User(
                uid=uuid4(),
                username="testuser",
                email="test@example.com",
                password_hash=get_password_hash("SecurePassword123!"),
                last_name="User",
                role=PublicUserRole.VIEWER,
                is_active=True,
                is_verified=True,
            )

        # Create and yield test client
        with TestClient(app) as test_client:
            yield test_client

    # Clear overrides after test
    app.dependency_overrides.clear()


# ============================================================================
# Mock Fixtures for External Services
# ============================================================================


@pytest.fixture
def mock_redis():
    """
    Mock Redis client for rate limiting and token blocklist.
    """
    with patch("app.core.redis.token_blocklist") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get = AsyncMock(return_value=None)
        mock_instance.set = AsyncMock(return_value=True)
        mock_instance.setex = AsyncMock(return_value=True)
        mock_instance.delete = AsyncMock(return_value=True)
        mock_instance.exists = AsyncMock(return_value=False)
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def mock_rate_limiter():
    """
    Mock the Redis rate limiter decorator.
    """
    with patch("app.core.redis_rate_limiter.redis_rate_limit") as mock_limiter:
        # Make the decorator do nothing (just return the original function)
        mock_limiter.return_value = lambda f: f
        yield mock_limiter


@pytest.fixture
def mock_email():
    """
    Mock email sending functionality.
    """
    with patch("app.api.v1.https.auth.send_email") as mock_send:
        mock_send.return_value = None
        yield mock_send


@pytest.fixture
def mock_add_jti_to_blocklist():
    """
    Mock the add_jti_to_blocklist function.
    """
    with patch(
        "app.core.redis.add_jti_to_blocklist", new_callable=AsyncMock
    ) as mock_func:
        mock_func.return_value = None
        yield mock_func


# ============================================================================
# Pytest Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle async tests properly."""
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)
