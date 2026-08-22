"""
tests/conftest.py — Global pytest configuration for AhmedETAP test suite.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is at the front of sys.path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set test environment variables
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ENV", "test")
os.environ.setdefault("ENGINEERING_SERVICE_AUTH_DISABLED", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_etap.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-chars-long!")
os.environ.setdefault("ETAP_SECRET_KEY", "test-etap-secret-key-32-chars-long!")
os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("AUTH_RETURN_RESET_TOKEN", "true")

try:
    import matplotlib

    matplotlib.use("Agg")
except Exception:
    pass


@pytest.fixture(autouse=True)
async def _init_test_database():
    """Ensure database tables exist and test users are seeded for all tests."""
    from sqlalchemy import select

    from api.auth import User, _hash_password
    from api.database import async_session, init_db

    await init_db()

    async with async_session() as session:
        res = await session.execute(select(User).where(User.id == "test-user-id"))
        user = res.scalar_one_or_none()
        if user is None:
            users = [
                User(
                    id="test-user-id",
                    username="testuser",
                    email="testuser@example.com",
                    password_hash=_hash_password("Str0ngP@ss!"),
                    role="engineer",
                    is_active=True,
                ),
                User(
                    id="test-admin-id",
                    username="admin",
                    email="admin@example.com",
                    password_hash=_hash_password("Str0ngP@ss!"),
                    role="admin",
                    is_active=True,
                ),
                User(
                    id="test-operator-id",
                    username="operator",
                    email="operator@example.com",
                    password_hash=_hash_password("Str0ngP@ss!"),
                    role="operator",
                    is_active=True,
                ),
                User(
                    id="test-viewer-id",
                    username="viewer",
                    email="viewer@example.com",
                    password_hash=_hash_password("Str0ngP@ss!"),
                    role="viewer",
                    is_active=True,
                ),
            ]
            session.add_all(users)
            await session.commit()
        else:
            user.email = "testuser@example.com"
            user.role = "engineer"
            user.password_hash = _hash_password("Str0ngP@ss!")
            user.is_active = True
            await session.commit()
    yield


@pytest.fixture
def registered_user():
    """Return dict of the default registered test user."""
    return {
        "id": "test-user-id",
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "Str0ngP@ss!",
        "role": "engineer",
    }


@pytest.fixture
def app():
    """Return canonical FastAPI application."""
    from api.routes import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app):
    """Return standard TestClient for synchronous API testing."""
    from starlette.testclient import TestClient

    from api.csrf import generate_csrf_token

    c = TestClient(app)
    c.headers.update({"x-csrf-token": generate_csrf_token()})
    return c


@pytest.fixture
def admin_headers():
    """Return headers for an admin user."""
    from api.auth import _create_access_token
    from api.csrf import generate_csrf_token

    token = _create_access_token("test-admin-id", role="admin")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": generate_csrf_token(),
    }


@pytest.fixture
def auth_headers():
    """Return default authenticated headers (testuser)."""
    from api.auth import _create_access_token
    from api.csrf import generate_csrf_token

    token = _create_access_token("test-user-id", role="engineer")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": generate_csrf_token(),
    }


@pytest.fixture
def operator_headers():
    """Return headers for an operator user."""
    from api.auth import _create_access_token
    from api.csrf import generate_csrf_token

    token = _create_access_token("test-operator-id", role="operator")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": generate_csrf_token(),
    }


@pytest.fixture
def viewer_headers():
    """Return headers for a viewer user."""
    from api.auth import _create_access_token
    from api.csrf import generate_csrf_token

    token = _create_access_token("test-viewer-id", role="viewer")
    return {
        "Authorization": f"Bearer {token}",
        "X-CSRF-Token": generate_csrf_token(),
    }
