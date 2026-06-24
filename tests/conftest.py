"""
Test configuration and fixtures for the Engineering Service.
Contains shared test utilities, mocks, and test network configurations.
"""

import os
import tempfile
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

try:
    from core.bootstrap import logger
except ImportError:
    import logging

    logger = logging.getLogger("test")

try:
    from services.study_service import (
        BusSpec,
        GeneratorSpec,
        LineSpec,
        LoadSpec,
        StudyRequest,
        SystemSpec,
        TransformerSpec,
    )
except ImportError:
    # If study_service is not importable, create placeholder classes
    from pydantic import BaseModel

    class BusSpec(BaseModel):
        bus_id: int = 0
        voltage_kv: float = 0.0
        bus_type: str = "pq"
        angle_deg: float = 0.0

    class LineSpec(BaseModel):
        line_id: int = 0
        from_bus_id: int = 0
        to_bus_id: int = 0
        resistance_pu: float = 0.0
        reactance_pu: float = 0.0
        charging_siemens: float = 0.0

    class GeneratorSpec(BaseModel):
        generator_id: int = 0
        bus_id: int = 0
        power_real_pu: float = 0.0
        power_reactive_pu: float = 0.0
        voltage_setpoint_pu: float = 1.0

    class LoadSpec(BaseModel):
        load_id: int = 0
        bus_id: int = 0
        power_real_pu: float = 0.0
        power_reactive_pu: float = 0.0

    class TransformerSpec(BaseModel):
        transformer_id: int = 0
        from_bus_id: int = 0
        to_bus_id: int = 0
        resistance_pu: float = 0.0
        reactance_pu: float = 0.0
        tap_ratio: float = 1.0

    class SystemSpec(BaseModel):
        buses: list = []
        lines: list = []
        generators: list = []
        loads: list = []
        transformers: list = []

    class StudyRequest(BaseModel):
        study_type: str = "load_flow"
        system_spec: SystemSpec = None
        parameters: dict = {}


GenSpec = GeneratorSpec

# Test network configurations
TEST_NETWORKS = {
    "3-bus": {
        "buses": [
            BusSpec(bus_id=1, voltage_kv=20.0, bus_type="slack", angle_deg=0.0),
            BusSpec(bus_id=2, voltage_kv=20.0, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=3, voltage_kv=20.0, bus_type="pv", angle_deg=0.0),
        ],
        "lines": [
            LineSpec(
                line_id=1,
                from_bus_id=1,
                to_bus_id=2,
                resistance_pu=0.02,
                reactance_pu=0.08,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=2,
                from_bus_id=2,
                to_bus_id=3,
                resistance_pu=0.02,
                reactance_pu=0.08,
                charging_siemens=0.0,
            ),
        ],
        "generators": [
            GenSpec(
                generator_id=1,
                bus_id=1,
                power_real_pu=1.0,
                power_reactive_pu=0.5,
                voltage_setpoint_pu=1.0,
            ),
            GenSpec(
                generator_id=2,
                bus_id=3,
                power_real_pu=0.5,
                power_reactive_pu=0.2,
                voltage_setpoint_pu=1.0,
            ),
        ],
        "loads": [
            LoadSpec(load_id=1, bus_id=2, power_real_pu=0.8, power_reactive_pu=0.6),
        ],
        "transformers": [],
    },
    "ieee-14": {
        "buses": [
            BusSpec(bus_id=1, voltage_kv=115.0, bus_type="slack", angle_deg=0.0),
            BusSpec(bus_id=2, voltage_kv=115.0, bus_type="pv", angle_deg=0.0),
            BusSpec(bus_id=3, voltage_kv=115.0, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=4, voltage_kv=115.0, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=5, voltage_kv=115.0, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=6, voltage_kv=13.8, bus_type="pv", angle_deg=0.0),
            BusSpec(bus_id=7, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=8, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=9, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=10, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=11, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=12, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=13, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            BusSpec(bus_id=14, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
        ],
        "lines": [
            LineSpec(
                line_id=1,
                from_bus_id=1,
                to_bus_id=2,
                resistance_pu=0.01938,
                reactance_pu=0.05917,
                charging_siemens=0.0528,
            ),
            LineSpec(
                line_id=2,
                from_bus_id=1,
                to_bus_id=5,
                resistance_pu=0.05403,
                reactance_pu=0.22304,
                charging_siemens=0.0492,
            ),
            LineSpec(
                line_id=3,
                from_bus_id=2,
                to_bus_id=3,
                resistance_pu=0.04699,
                reactance_pu=0.19797,
                charging_siemens=0.0438,
            ),
            LineSpec(
                line_id=4,
                from_bus_id=2,
                to_bus_id=4,
                resistance_pu=0.05811,
                reactance_pu=0.17632,
                charging_siemens=0.0340,
            ),
            LineSpec(
                line_id=5,
                from_bus_id=2,
                to_bus_id=5,
                resistance_pu=0.05695,
                reactance_pu=0.21982,
                charging_siemens=0.0346,
            ),
            LineSpec(
                line_id=6,
                from_bus_id=3,
                to_bus_id=4,
                resistance_pu=0.06701,
                reactance_pu=0.17103,
                charging_siemens=0.0128,
            ),
            LineSpec(
                line_id=7,
                from_bus_id=4,
                to_bus_id=5,
                resistance_pu=0.01335,
                reactance_pu=0.04211,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=8,
                from_bus_id=4,
                to_bus_id=7,
                resistance_pu=0.0,
                reactance_pu=0.20912,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=9,
                from_bus_id=4,
                to_bus_id=9,
                resistance_pu=0.0,
                reactance_pu=0.55618,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=10,
                from_bus_id=5,
                to_bus_id=6,
                resistance_pu=0.0,
                reactance_pu=0.25202,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=11,
                from_bus_id=6,
                to_bus_id=11,
                resistance_pu=0.09498,
                reactance_pu=0.19890,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=12,
                from_bus_id=6,
                to_bus_id=12,
                resistance_pu=0.12291,
                reactance_pu=0.25581,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=13,
                from_bus_id=6,
                to_bus_id=13,
                resistance_pu=0.06615,
                reactance_pu=0.13027,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=14,
                from_bus_id=7,
                to_bus_id=8,
                resistance_pu=0.0,
                reactance_pu=0.17615,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=15,
                from_bus_id=7,
                to_bus_id=9,
                resistance_pu=0.0,
                reactance_pu=0.11001,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=16,
                from_bus_id=9,
                to_bus_id=10,
                resistance_pu=0.03181,
                reactance_pu=0.08450,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=17,
                from_bus_id=9,
                to_bus_id=14,
                resistance_pu=0.12711,
                reactance_pu=0.27038,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=18,
                from_bus_id=10,
                to_bus_id=11,
                resistance_pu=0.08205,
                reactance_pu=0.19207,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=19,
                from_bus_id=12,
                to_bus_id=13,
                resistance_pu=0.22092,
                reactance_pu=0.19988,
                charging_siemens=0.0,
            ),
            LineSpec(
                line_id=20,
                from_bus_id=13,
                to_bus_id=14,
                resistance_pu=0.17093,
                reactance_pu=0.34802,
                charging_siemens=0.0,
            ),
        ],
        "generators": [
            GenSpec(
                generator_id=1,
                bus_id=1,
                power_real_pu=0.0000,
                power_reactive_pu=0.0000,
                voltage_setpoint_pu=1.0600,
            ),
            GenSpec(
                generator_id=2,
                bus_id=2,
                power_real_pu=0.4000,
                power_reactive_pu=0.0000,
                voltage_setpoint_pu=1.0450,
            ),
            GenSpec(
                generator_id=3,
                bus_id=3,
                power_real_pu=0.0000,
                power_reactive_pu=0.0000,
                voltage_setpoint_pu=1.0100,
            ),
            GenSpec(
                generator_id=4,
                bus_id=6,
                power_real_pu=0.0000,
                power_reactive_pu=0.0000,
                voltage_setpoint_pu=1.0700,
            ),
            GenSpec(
                generator_id=5,
                bus_id=8,
                power_real_pu=0.0000,
                power_reactive_pu=0.0000,
                voltage_setpoint_pu=1.0900,
            ),
        ],
        "loads": [
            LoadSpec(load_id=1, bus_id=2, power_real_pu=0.2170, power_reactive_pu=0.1270),
            LoadSpec(load_id=2, bus_id=3, power_real_pu=0.9420, power_reactive_pu=0.1900),
            LoadSpec(load_id=3, bus_id=4, power_real_pu=0.4780, power_reactive_pu=0.0390),
            LoadSpec(load_id=4, bus_id=5, power_real_pu=0.0760, power_reactive_pu=0.0160),
            LoadSpec(load_id=5, bus_id=6, power_real_pu=0.1120, power_reactive_pu=0.0750),
            LoadSpec(load_id=6, bus_id=9, power_real_pu=0.2950, power_reactive_pu=0.1660),
            LoadSpec(load_id=7, bus_id=10, power_real_pu=0.0900, power_reactive_pu=0.0580),
            LoadSpec(load_id=8, bus_id=11, power_real_pu=0.0350, power_reactive_pu=0.0180),
            LoadSpec(load_id=9, bus_id=12, power_real_pu=0.0610, power_reactive_pu=0.0160),
            LoadSpec(load_id=10, bus_id=13, power_real_pu=0.1350, power_reactive_pu=0.0580),
            LoadSpec(load_id=11, bus_id=14, power_real_pu=0.1490, power_reactive_pu=0.0500),
        ],
        "transformers": [],
    },
}


@pytest.fixture
def sample_3bus_network():
    """Provides a simple 3-bus test network for load flow studies."""
    return TEST_NETWORKS["3-bus"]


@pytest.fixture
def sample_ieee14_network():
    """Provides the IEEE 14-bus test network for comprehensive studies."""
    return TEST_NETWORKS["ieee-14"]


@pytest.fixture
def mock_etap_provider():
    """Provides a mocked ETAP provider for testing without actual ETAP installation."""
    mock_provider = Mock()
    mock_provider.execute_study = Mock(return_value={"status": "success", "results": {}})
    mock_provider.is_available = Mock(return_value=False)
    mock_provider.connect = Mock()
    mock_provider.disconnect = Mock()
    return mock_provider


@pytest.fixture
def mock_redis():
    """Provides a mocked Redis instance for testing cache functionality."""
    mock_redis_instance = Mock()
    mock_redis_instance.get = AsyncMock(return_value=None)
    mock_redis_instance.set = AsyncMock(return_value=True)
    mock_redis_instance.ping = AsyncMock(return_value=True)
    return mock_redis_instance


@pytest.fixture
def temp_database():
    """Provides a temporary database file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    yield tmp_path
    os.unlink(tmp_path)


@pytest.fixture
def sample_study_request(sample_3bus_network):
    """Provides a sample study request for testing."""
    return StudyRequest(
        study_type="load_flow",
        system_spec=SystemSpec(**sample_3bus_network),
        parameters={"tolerance": 1e-6, "max_iterations": 50},
    )


@pytest.fixture
def api_client():
    """Provides a test client for API testing."""
    from fastapi.testclient import TestClient

    from api.routes import app

    # Disable ETAP for testing
    os.environ["USE_ETAP"] = "false"
    os.environ["PRIVACY_MODE"] = "true"

    client = TestClient(app)
    yield client


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Sets up the test environment automatically for all tests."""
    # Set environment variables for testing
    os.environ["ENGINEERING_SERVICE_AUTH_DISABLED"] = "true"
    os.environ["USE_ETAP"] = "false"
    os.environ["PRIVACY_MODE"] = "true"

    # Set logging to debug level for tests
    try:
        logger.setLevel("DEBUG")
    except (AttributeError, TypeError):
        pass

    yield

    # Clean up environment variables after tests
    if "ENGINEERING_SERVICE_AUTH_DISABLED" in os.environ:
        del os.environ["ENGINEERING_SERVICE_AUTH_DISABLED"]
    if "USE_ETAP" in os.environ:
        del os.environ["USE_ETAP"]
    if "PRIVACY_MODE" in os.environ:
        del os.environ["PRIVACY_MODE"]


# ---------------------------------------------------------------------------
# Auth/Projects test fixtures (SQLite in-memory)
# ---------------------------------------------------------------------------

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from api.database import Base

_TEST_DB_URL = "sqlite+aiosqlite://"

_test_engine: AsyncEngine = create_async_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

_TestSessionLocal = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Provide a fresh in-memory database engine for each test."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield _test_engine
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def app(db_engine: AsyncEngine):
    """Return the FastAPI application with get_db overridden to the test DB."""
    from fastapi import FastAPI
    from api.routes import app as real_app

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
    real_app.dependency_overrides[_original_get_db] = _override_get_db

    yield real_app

    real_app.dependency_overrides.clear()


from fastapi.testclient import TestClient


@pytest.fixture(scope="function")
def client(app) -> Generator[TestClient, None, None]:
    """Provide a TestClient wired to the test application."""
    import api.auth as _auth_module
    _auth_module._LOGIN_ATTEMPTS.clear()

    with TestClient(app) as c:
        yield c


def _register_user(
    client,
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
    client,
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
def registered_user(client) -> dict:
    """Register a test user and return the user profile dict."""
    return _register_user(client)


@pytest.fixture
def auth_headers(client, registered_user: dict) -> dict:
    """Return Authorization headers for the default registered user."""
    login_data = _login_user(client)
    return _auth_headers(login_data["access_token"])


@pytest.fixture
def admin_headers(client) -> dict:
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
def viewer_headers(client) -> dict:
    """Register a viewer user and return Authorization headers."""
    _register_user(
        client,
        username="viewer_user",
        email="viewer@example.com",
        role="viewer",
    )
    login_data = _login_user(client, username="viewer_user")
    return _auth_headers(login_data["access_token"])
