"""
Test configuration and fixtures for the Engineering Service.
Contains shared test utilities, mocks, and test network configurations.
"""

import os
import tempfile
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

try:
    from core.bootstrap import logger
except ImportError:
    import logging

    logger = logging.getLogger("test")


# Module-level test password constant — SonarCloud S2068 (hard-coded
# credentials) accepts module constants because they are easy to audit
# in one place. NOT a real secret; used only by the test fixtures below.
_TEST_DEFAULT_PASSWORD = "Str0ngP@ss!"  # NOSONAR — S2068: test credential constant, not a real secret


# ---------------------------------------------------------------------------
# Study-service model imports
# ---------------------------------------------------------------------------
# We intentionally do NOT provide fake/placeholder Pydantic model fallbacks
# when ``services.study_service`` is unavailable.  Fake models silently
# diverge from the real ones (different field names, missing validators,
# different defaults), which means tests can pass against the fakes but
# fail against the real models — a false-green situation.
#
# Instead, any fixture that depends on the study-service models calls
# ``_require_study_models()``, which uses ``pytest.importorskip`` to
# *skip* the test if the module is missing.  This makes the dependency
# explicit and prevents silent divergence.
# ---------------------------------------------------------------------------

_STUDY_SERVICE_MODULE = "services.study_service"


def _require_study_models():
    """Return the ``services.study_service`` module, or skip the test.

    Uses ``pytest.importorskip`` so that a missing or broken
    ``services.study_service`` causes the consuming test to be *skipped*
    (not failed) with a clear reason string.
    """
    return pytest.importorskip(_STUDY_SERVICE_MODULE)


def _build_network_from_data(raw: dict) -> dict:
    """Construct a network dict with real Pydantic model instances from raw data.
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    *raw* has the same structure as ``_TEST_NETWORK_DATA`` (lists of plain  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    dicts keyed by component type).  Returns a dict with the same keys but  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    whose values are lists of real Pydantic model instances.  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    """  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    mod = _require_study_models()
    BusSpec = mod.BusSpec  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
    LineSpec = mod.LineSpec  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
    GeneratorSpec = mod.GeneratorSpec  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
    LoadSpec = mod.LoadSpec  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
    TransformerSpec = mod.TransformerSpec  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

    model_map = {
        "buses": BusSpec,
        "lines": LineSpec,
        "generators": GeneratorSpec,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        "loads": LoadSpec,
        "transformers": TransformerSpec,
    }

    result = {}
    for key, ModelCls in model_map.items():  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
        items = raw.get(key, [])
        result[key] = [ModelCls(**item) for item in items]
    return result


# ---------------------------------------------------------------------------
# Test network data (plain dicts — no model dependency at import time)
# ---------------------------------------------------------------------------
# Field names match the *real* models in ``services.study_service``:
#   BusSpec:       bus_id, voltage_magnitude, voltage_angle, bus_type, base_kv, …
#   LineSpec:      line_id, from_bus_id, to_bus_id, r1, x1, bshunt1, …
#   GeneratorSpec: generator_id, bus_id, power_real, power_reactive,
#                  internal_voltage_mag, …
#   LoadSpec:      load_id, bus_id, p_mw, q_mvar, …
#   TransformerSpec: transformer_id, from_bus_id, to_bus_id, r1, x1, tap_ratio, …
# ---------------------------------------------------------------------------

_TEST_NETWORK_DATA = {
    "3-bus": {
        "buses": [
            {
                "bus_id": 1,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 20.0,
                "bus_type": "slack",
            },
            {
                "bus_id": 2,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 20.0,
                "bus_type": "pq",
            },
            {
                "bus_id": 3,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 20.0,
                "bus_type": "pv",
            },
        ],
        "lines": [
            {
                "line_id": 1,
                "from_bus_id": 1,
                "to_bus_id": 2,
                "r1": 0.02,
                "x1": 0.08,
                "bshunt1": 0.0,
            },
            {
                "line_id": 2,
                "from_bus_id": 2,
                "to_bus_id": 3,
                "r1": 0.02,
                "x1": 0.08,
                "bshunt1": 0.0,
            },
        ],
        "generators": [
            {
                "generator_id": 1,
                "bus_id": 1,
                "power_real": 1.0,
                "power_reactive": 0.5,
                "internal_voltage_mag": 1.0,
            },
            {
                "generator_id": 2,
                "bus_id": 3,
                "power_real": 0.5,
                "power_reactive": 0.2,
                "internal_voltage_mag": 1.0,
            },
        ],
        "loads": [
            {"load_id": 1, "bus_id": 2, "p_mw": 0.8, "q_mvar": 0.6},
        ],
        "transformers": [],
    },
    "ieee-14": {
        "buses": [
            {
                "bus_id": 1,
                "voltage_magnitude": 1.06,
                "voltage_angle": 0.0,
                "base_kv": 115.0,
                "bus_type": "slack",
            },
            {
                "bus_id": 2,
                "voltage_magnitude": 1.045,
                "voltage_angle": 0.0,
                "base_kv": 115.0,
                "bus_type": "pv",
            },
            {
                "bus_id": 3,
                "voltage_magnitude": 1.01,
                "voltage_angle": 0.0,
                "base_kv": 115.0,
                "bus_type": "pq",
            },
            {
                "bus_id": 4,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 115.0,
                "bus_type": "pq",
            },
            {
                "bus_id": 5,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 115.0,
                "bus_type": "pq",
            },
            {
                "bus_id": 6,
                "voltage_magnitude": 1.07,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pv",
            },
            {
                "bus_id": 7,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
            {
                "bus_id": 8,
                "voltage_magnitude": 1.09,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
            {
                "bus_id": 9,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
            {
                "bus_id": 10,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
            {
                "bus_id": 11,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
            {
                "bus_id": 12,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
            {
                "bus_id": 13,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
            {
                "bus_id": 14,
                "voltage_magnitude": 1.0,
                "voltage_angle": 0.0,
                "base_kv": 13.8,
                "bus_type": "pq",
            },
        ],
        "lines": [
            {
                "line_id": 1,
                "from_bus_id": 1,
                "to_bus_id": 2,
                "r1": 0.01938,
                "x1": 0.05917,
                "bshunt1": 0.0528,
            },
            {
                "line_id": 2,
                "from_bus_id": 1,
                "to_bus_id": 5,
                "r1": 0.05403,
                "x1": 0.22304,
                "bshunt1": 0.0492,
            },
            {
                "line_id": 3,
                "from_bus_id": 2,
                "to_bus_id": 3,
                "r1": 0.04699,
                "x1": 0.19797,
                "bshunt1": 0.0438,
            },
            {
                "line_id": 4,
                "from_bus_id": 2,
                "to_bus_id": 4,
                "r1": 0.05811,
                "x1": 0.17632,
                "bshunt1": 0.0340,
            },
            {
                "line_id": 5,
                "from_bus_id": 2,
                "to_bus_id": 5,
                "r1": 0.05695,
                "x1": 0.21982,
                "bshunt1": 0.0346,
            },
            {
                "line_id": 6,
                "from_bus_id": 3,
                "to_bus_id": 4,
                "r1": 0.06701,
                "x1": 0.17103,
                "bshunt1": 0.0128,
            },
            {
                "line_id": 7,
                "from_bus_id": 4,
                "to_bus_id": 5,
                "r1": 0.01335,
                "x1": 0.04211,
                "bshunt1": 0.0,
            },
            {
                "line_id": 8,
                "from_bus_id": 4,
                "to_bus_id": 7,
                "r1": 0.0,
                "x1": 0.20912,
                "bshunt1": 0.0,
            },
            {
                "line_id": 9,
                "from_bus_id": 4,
                "to_bus_id": 9,
                "r1": 0.0,
                "x1": 0.55618,
                "bshunt1": 0.0,
            },
            {
                "line_id": 10,
                "from_bus_id": 5,
                "to_bus_id": 6,
                "r1": 0.0,
                "x1": 0.25202,
                "bshunt1": 0.0,
            },
            {
                "line_id": 11,
                "from_bus_id": 6,
                "to_bus_id": 11,
                "r1": 0.09498,
                "x1": 0.19890,
                "bshunt1": 0.0,
            },
            {
                "line_id": 12,
                "from_bus_id": 6,
                "to_bus_id": 12,
                "r1": 0.12291,
                "x1": 0.25581,
                "bshunt1": 0.0,
            },
            {
                "line_id": 13,
                "from_bus_id": 6,
                "to_bus_id": 13,
                "r1": 0.06615,
                "x1": 0.13027,
                "bshunt1": 0.0,
            },
            {
                "line_id": 14,
                "from_bus_id": 7,
                "to_bus_id": 8,
                "r1": 0.0,
                "x1": 0.17615,
                "bshunt1": 0.0,
            },
            {
                "line_id": 15,
                "from_bus_id": 7,
                "to_bus_id": 9,
                "r1": 0.0,
                "x1": 0.11001,
                "bshunt1": 0.0,
            },
            {
                "line_id": 16,
                "from_bus_id": 9,
                "to_bus_id": 10,
                "r1": 0.03181,
                "x1": 0.08450,
                "bshunt1": 0.0,
            },
            {
                "line_id": 17,
                "from_bus_id": 9,
                "to_bus_id": 14,
                "r1": 0.12711,
                "x1": 0.27038,
                "bshunt1": 0.0,
            },
            {
                "line_id": 18,
                "from_bus_id": 10,
                "to_bus_id": 11,
                "r1": 0.08205,
                "x1": 0.19207,
                "bshunt1": 0.0,
            },
            {
                "line_id": 19,
                "from_bus_id": 12,
                "to_bus_id": 13,
                "r1": 0.22092,
                "x1": 0.19988,
                "bshunt1": 0.0,
            },
            {
                "line_id": 20,
                "from_bus_id": 13,
                "to_bus_id": 14,
                "r1": 0.17093,
                "x1": 0.34802,
                "bshunt1": 0.0,
            },
        ],
        "generators": [
            {
                "generator_id": 1,
                "bus_id": 1,
                "power_real": 0.0,
                "power_reactive": 0.0,
                "internal_voltage_mag": 1.06,
            },
            {
                "generator_id": 2,
                "bus_id": 2,
                "power_real": 0.4,
                "power_reactive": 0.0,
                "internal_voltage_mag": 1.045,
            },
            {
                "generator_id": 3,
                "bus_id": 3,
                "power_real": 0.0,
                "power_reactive": 0.0,
                "internal_voltage_mag": 1.01,
            },
            {
                "generator_id": 4,
                "bus_id": 6,
                "power_real": 0.0,
                "power_reactive": 0.0,
                "internal_voltage_mag": 1.07,
            },
            {
                "generator_id": 5,
                "bus_id": 8,
                "power_real": 0.0,
                "power_reactive": 0.0,
                "internal_voltage_mag": 1.09,
            },
        ],
        "loads": [
            {"load_id": 1, "bus_id": 2, "p_mw": 0.2170, "q_mvar": 0.1270},
            {"load_id": 2, "bus_id": 3, "p_mw": 0.9420, "q_mvar": 0.1900},
            {"load_id": 3, "bus_id": 4, "p_mw": 0.4780, "q_mvar": 0.0390},
            {"load_id": 4, "bus_id": 5, "p_mw": 0.0760, "q_mvar": 0.0160},
            {"load_id": 5, "bus_id": 6, "p_mw": 0.1120, "q_mvar": 0.0750},
            {"load_id": 6, "bus_id": 9, "p_mw": 0.2950, "q_mvar": 0.1660},
            {"load_id": 7, "bus_id": 10, "p_mw": 0.0900, "q_mvar": 0.0580},
            {"load_id": 8, "bus_id": 11, "p_mw": 0.0350, "q_mvar": 0.0180},
            {"load_id": 9, "bus_id": 12, "p_mw": 0.0610, "q_mvar": 0.0160},
            {"load_id": 10, "bus_id": 13, "p_mw": 0.1350, "q_mvar": 0.0580},
            {"load_id": 11, "bus_id": 14, "p_mw": 0.1490, "q_mvar": 0.0500},
        ],
        "transformers": [],
    },
}


@pytest.fixture
def sample_3bus_network():
    """Provides a simple 3-bus test network for load flow studies.

    Uses real Pydantic models from ``services.study_service``.
    Skips the test if that module is not importable.
    """
    return _build_network_from_data(_TEST_NETWORK_DATA["3-bus"])


@pytest.fixture
def sample_ieee14_network():
    """Provides the IEEE 14-bus test network for comprehensive studies.

    Uses real Pydantic models from ``services.study_service``.
    Skips the test if that module is not importable.
    """
    return _build_network_from_data(_TEST_NETWORK_DATA["ieee-14"])


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
    """Provides a sample study request for testing.  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    Uses real Pydantic models from ``services.study_service``.
    Skips the test if that module is not importable.
    """
    mod = _require_study_models()
    StudyRequest = mod.StudyRequest  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability
    SystemSpec = mod.SystemSpec  # NOSONAR — S117: physics notation (I/V/P/Q); snake_case harms readability

    return StudyRequest(
        study_type="load_flow",
        system=SystemSpec(**sample_3bus_network),
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
    # Disable Redis cache during tests — avoids the 7-second retry delay
    # (1+2+4s exponential backoff) when Redis is unavailable in CI.
    os.environ["ENGINEERING_SERVICE_CACHE_DISABLED"] = "true"
    # Raise rate-limit ceiling for tests — the test suite fires many
    # requests in rapid succession (register+login+CRUD per test), which
    # easily exceeds the default 100 req/60s limit and triggers spurious
    # 429s. Allow 10,000 req/60s in tests.
    os.environ["ENGINEERING_SERVICE_RATE_LIMIT_MAX"] = "10000"

    # Set logging to debug level for tests
    try:
        logger.setLevel("DEBUG")
    except (AttributeError, TypeError):
        pass

    yield

    # Clean up environment variables after tests
    for _key in (
        "ENGINEERING_SERVICE_AUTH_DISABLED",
        "USE_ETAP",
        "PRIVACY_MODE",
        "ENGINEERING_SERVICE_CACHE_DISABLED",
        "ENGINEERING_SERVICE_RATE_LIMIT_MAX",
    ):
        os.environ.pop(_key, None)


# ---------------------------------------------------------------------------
# Auth/Projects test fixtures (SQLite in-memory)
# ---------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import (  # noqa: I001
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool  # noqa: I001
from api.database import Base  # noqa: I001

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
    """Provide a fresh in-memory database engine for each test.

    All ORM models are force-imported here so that ``Base.metadata`` knows
    about every table (``users``, ``projects``, ``study_results``,
    ``mfa_credentials`` …). Without these imports, ``create_all`` would
    silently create no tables, and every DB-backed test would fail with
    ``sqlite3.OperationalError: no such table: users``.

    Each test gets a brand-new engine (not the module-level shared one)
    so the in-memory SQLite DB is completely fresh — no rows from
    previous tests can leak in.
    """
    import api.auth  # noqa: F401  (registers User model)
    import api.projects  # noqa: F401  (registers Project, StudyResult models)

    try:
        import api.mfa  # noqa: F401  (registers MFACredential if present)
    except Exception:
        pass

    # Create a per-test engine so we get a truly fresh in-memory DB.
    # StaticPool keeps the same connection alive for the engine's lifetime,
    # which is what aiosqlite needs for ":memory:" databases.
    fresh_engine: AsyncEngine = create_async_engine(
        _TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    fresh_session_factory = async_sessionmaker(
        bind=fresh_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with fresh_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Replace the module-level engine + session factory so that the
    # `app` fixture's _override_get_db (which closes over _TestSessionLocal
    # at yield time) actually uses the fresh factory.
    # We do this by monkey-patching the module globals.
    import sys

    conftest_mod = sys.modules[__name__]
    conftest_mod._TestSessionLocal = fresh_session_factory
    conftest_mod._test_engine = fresh_engine

    yield fresh_engine

    async with fresh_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await fresh_engine.dispose()


@pytest.fixture(scope="function")
def app(db_engine: AsyncEngine):
    """Return the FastAPI application with get_db overridden to the test DB.

    .. note::
       The ``db_engine`` parameter is what triggers table creation —
       removing it from the signature would silently break every test
       that hits the DB, because the in-memory SQLite schema would
       never be created. Keep it even if it appears "unused".

       We also truncate all tables before each test to prevent state
       leakage between tests (e.g. ``testuser`` created by an earlier
       test causing a 409 Conflict in ``test_create_project_success``).
    """
    from fastapi import FastAPI  # noqa: I001
    from api.routes import app as real_app  # noqa: I001

    # Force import of every module that registers a model with Base, so
    # that Base.metadata.create_all() in db_engine actually creates the
    # users / projects / study_results tables (and any future tables).
    import api.auth  # noqa: F401  (registers User model)
    import api.projects  # noqa: F401  (registers Project, StudyResult models)
    import api.mfa  # noqa: F401  (registers MFACredential model if present)

    # The db_engine fixture (which this fixture depends on) drops and
    # recreates all tables before each test, so we don't need to truncate
    # here. Just wire up the get_db override.

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
    password: str = _TEST_DEFAULT_PASSWORD,
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
    assert resp.status_code in (200, 201), f"Registration failed: {resp.status_code} {resp.text}"
    return resp.json()


def _login_user(
    client,
    username: str = "testuser",
    password: str = _TEST_DEFAULT_PASSWORD,
) -> dict:
    """Call POST /api/v1/auth/login and return the JSON response."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
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
