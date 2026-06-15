"""
Shared pytest fixtures for ETAP AI Platform API tests.

Provides:
- In-memory SQLite database (async via aiosqlite)
- FastAPI TestClient with overridden get_db dependency
- Helper factories for creating test users and obtaining JWT tokens
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Re-export Base from api.database so we can reference it before importing
# models that register themselves on Base.metadata.
# ---------------------------------------------------------------------------

# Also import the ORM models so create_all knows about them
import api.auth  # noqa: F401
import api.projects  # noqa: F401

# Import routers *after* Base is available so ORM models register their
# tables on Base.metadata.
from api.auth import router as auth_router  # noqa: E402
from api.database import Base  # noqa: E402
from api.dependencies import (  # noqa: E402
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    CurrentUser,
)
from api.projects import router as projects_router  # noqa: E402

# ---------------------------------------------------------------------------
# In-memory async SQLite engine
# ---------------------------------------------------------------------------

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_test_engine: AsyncEngine = create_async_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # required for in-memory SQLite to share state
    echo=False,
)

_TestSessionLocal = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI application factory for tests
# ---------------------------------------------------------------------------

def _create_test_app() -> FastAPI:
    """Build a minimal FastAPI app that includes all API routers."""
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(projects_router)
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Provide a fresh in-memory database engine for each test.

    Tables are created before and dropped after every test so that
    tests are fully isolated.
    """
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _test_engine
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app(db_engine: AsyncEngine) -> FastAPI:
    """Return a FastAPI application with ``get_db`` overridden to the test DB."""
    application = _create_test_app()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with _TestSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    from api.database import get_db as _original_get_db
    application.dependency_overrides[_original_get_db] = _override_get_db

    return application


@pytest.fixture(scope="function")
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    """Provide a ``TestClient`` wired to the test application."""
    # Reset the in-memory login rate limiter between tests so that
    # failures in one test do not bleed into the next.
    import api.auth as _auth_module
    _auth_module._LOGIN_ATTEMPTS.clear()

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: create a user via the register endpoint and return auth headers
# ---------------------------------------------------------------------------

def _register_user(
    client: TestClient,
    username: str = "testuser",
    email: str = "testuser@example.com",
    password: str = "Str0ngP@ss!",
    role: str = "engineer",
) -> dict:
    """Call POST /api/v1/auth/register and return the JSON response."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "role": role,
        },
    )
    assert resp.status_code in (200, 201), (
        f"Registration failed: {resp.status_code} {resp.text}"
    )
    return resp.json()


def _login_user(
    client: TestClient,
    username: str = "testuser",
    password: str = "Str0ngP@ss!",
) -> dict:
    """Call POST /api/v1/auth/login and return the JSON response."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, (
        f"Login failed: {resp.status_code} {resp.text}"
    )
    return resp.json()


def _auth_headers(access_token: str) -> dict:
    """Return an Authorization header dict for the given token."""
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def registered_user(client: TestClient) -> dict:
    """Register a test user and return the user profile dict."""
    return _register_user(client)


@pytest.fixture
def auth_headers(client: TestClient, registered_user: dict) -> dict:
    """Return Authorization headers for the default registered user."""
    login_data = _login_user(client)
    return _auth_headers(login_data["access_token"])


@pytest.fixture
def admin_headers(client: TestClient) -> dict:
    """Register an admin user and return Authorization headers."""
    _register_user(
        client,
        username="admin_user",
        email="admin@example.com",
        role="admin",
    )
    login_data = _login_user(client, username="admin_user")
    return _auth_headers(login_data["access_token"])


@pytest.fixture
def viewer_headers(client: TestClient) -> dict:
    """Register a viewer user and return Authorization headers."""
    _register_user(
        client,
        username="viewer_user",
        email="viewer@example.com",
        role="viewer",
    )
    login_data = _login_user(client, username="viewer_user")
    return _auth_headers(login_data["access_token"])
