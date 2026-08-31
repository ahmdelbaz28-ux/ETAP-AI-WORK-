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
os.environ.setdefault("ENGINEERING_SERVICE_API_KEY", "test-key")
os.environ.setdefault("ENGINEERING_SERVICE_RATE_LIMIT_DISABLED", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./data/test_etap.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-chars-long!")
os.environ.setdefault("ETAP_SECRET_KEY", "test-etap-secret-key-32-chars-long!")
os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("AUTH_RETURN_RESET_TOKEN", "true")

# ─── pytest-xdist isolation ──────────────────────────────────────────────────
# CI runs pytest with `-n 4`. All workers share one process-wide DATABASE_URL,
# so four SQLite writers raced on the same file: fixtures died with
# "database is locked" during schema setup and mid-run users looked missing
# to auth dependencies (spurious 401s). Give each xdist worker its own
# SQLite file. Sequential runs (no xdist) keep the previous behaviour.
_XDIST_WORKER = os.environ.get("PYTEST_XDIST_WORKER", "")
if _XDIST_WORKER:
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./test_{_XDIST_WORKER}.db"

try:
    import matplotlib

    matplotlib.use("Agg")
except Exception:
    pass


@pytest.fixture(autouse=True)
def _reset_redis_singleton():
    """Reset the module-level async Redis client around every test.

    Documented contract (api/auth.py, _get_redis_client): the singleton binds
    to the event loop current at creation; TestClient spins a fresh loop per
    test, so a carried-over client raises 'RuntimeError: Event loop is closed'.
    """
    from api import auth as auth_module

    auth_module._redis_client = None
    auth_module._redis_client_loop = None
    try:
        from api import routes as routes_module

        routes_module._redis_client = None
        routes_module._rate_limit_fallback_store.clear()
    except Exception:
        pass
    yield
    auth_module._redis_client = None
    auth_module._redis_client_loop = None
    try:
        from api import routes as routes_module

        routes_module._redis_client = None
        routes_module._rate_limit_fallback_store.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_chat_first_module_state():
    """Reset chat-first (P1–P4a) module-level state around every test.

    ``api.approvals._session_auto_approve`` and the agent-executor plan
    store are process-global dicts. pytest-xdist redistributes test order
    per worker, so keys leaked by one test flip the outcome of another
    (auto-approve assertions, idempotency replays, forged-plan checks).
    Clear them before and after each test to make outcomes order-safe.
    """
    approvals_module = None
    agent_executor_module = None
    try:
        import api.approvals as approvals_module  # noqa: F811
    except Exception:
        pass
    try:
        import api.agent_executor as agent_executor_module  # noqa: F811
    except Exception:
        pass

    def _clear() -> None:
        if approvals_module is not None:
            approvals_module._session_auto_approve.clear()
        if agent_executor_module is not None:
            agent_executor_module.reset_agent_exec_state()
        try:
            import api.chat_stream as chat_stream_module

            chat_stream_module.reset_chat_rate_limiter()
        except Exception:
            pass

    _clear()
    yield
    _clear()


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
                    tenant_id="",  # match SQLite-seed semantics (empty tenant) and satisfy users.tenant_id NOT NULL on Postgres
                    username="testuser",
                    email="testuser@example.com",
                    password_hash=_hash_password("Str0ngP@ss!"),
                    role="engineer",
                    is_active=True,
                ),
                User(
                    id="test-admin-id",
                    tenant_id="",  # match SQLite-seed semantics (empty tenant) and satisfy users.tenant_id NOT NULL on Postgres
                    username="admin",
                    email="admin@example.com",
                    password_hash=_hash_password("Str0ngP@ss!"),
                    role="admin",
                    is_active=True,
                ),
                User(
                    id="test-operator-id",
                    tenant_id="",  # match SQLite-seed semantics (empty tenant) and satisfy users.tenant_id NOT NULL on Postgres
                    username="operator",
                    email="operator@example.com",
                    password_hash=_hash_password("Str0ngP@ss!"),
                    # "operator" violates ck_users_role (migration 002 allows
                    # admin/engineer/analyst/viewer/guest) — use "analyst".
                    role="analyst",
                    is_active=True,
                ),
                User(
                    id="test-viewer-id",
                    tenant_id="",  # match SQLite-seed semantics (empty tenant) and satisfy users.tenant_id NOT NULL on Postgres
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
    # When the service under test enforces API-key auth (e.g. CI sets
    # ENGINEERING_SERVICE_API_KEY), attach the same key so requests pass
    # _require_api_key instead of failing with 401 before exercising the
    # endpoint logic. No-op when the variable is unset (local dev).
    api_key = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
    if api_key:
        c.headers.update({"x-api-key": api_key})
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

    token = _create_access_token("test-operator-id", role="analyst")
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


@pytest.fixture
def api_client(client):
    """Return a synchronous TestClient (alias of ``client``).

    Integration tests under tests/integration/ use this name to make the
    API-under-test explicit; it is the same client with CSRF pre-set.
    """
    return client


@pytest.fixture
def sample_3bus_network():
    """Return a minimal 3-bus system as a SystemSpec-compatible mapping.

    Values are dictionaries compatible with SystemSpec validation.
    """
    from core_model.specs import BusSpec, GeneratorSpec, LineSpec, LoadSpec

    return {
        "base_mva": 100.0,
        "buses": [
            BusSpec(
                bus_id=1,
                bus_type="slack",
                base_kv=20.0,
                voltage_magnitude=1.0,
                voltage_angle=0.0,
            ).model_dump(),
            BusSpec(bus_id=2, bus_type="pq", base_kv=20.0).model_dump(),
            BusSpec(bus_id=3, bus_type="pv", base_kv=20.0).model_dump(),
        ],
        "lines": [
            LineSpec(
                line_id=1, from_bus_id=1, to_bus_id=2, r1=0.02, x1=0.08, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=2, from_bus_id=2, to_bus_id=3, r1=0.02, x1=0.08, bshunt1=0.0
            ).model_dump(),
        ],
        "generators": [
            GeneratorSpec(generator_id=1, bus_id=1, internal_voltage_mag=1.0).model_dump(),
        ],
        "loads": [
            LoadSpec(load_id=1, bus_id=2, p_mw=40.0, q_mvar=10.0).model_dump(),
        ],
    }


@pytest.fixture
def sample_ieee14_network():
    """Return a standard IEEE-14 bus test system.

    This is the classic IEEE 14-bus benchmark system used for testing
    load flow, fault analysis, and other power system studies.
    Bus 1 is slack, buses 2,3,6,7,8,9 are PV, buses 4,5 are PQ loads.
    """
    from core_model.specs import BusSpec, GeneratorSpec, LineSpec, LoadSpec, TransformerSpec

    return {
        "base_mva": 100.0,
        "buses": [
            BusSpec(
                bus_id=1, bus_type="slack", base_kv=230.0, voltage_magnitude=1.0, voltage_angle=0.0
            ).model_dump(),
            BusSpec(
                bus_id=2,
                bus_type="pv",
                base_kv=230.0,
                voltage_magnitude=1.0,
                generation_power_real=40.0,
                generation_power_imag=-10.0,
            ).model_dump(),
            BusSpec(
                bus_id=3, bus_type="pq", base_kv=230.0, load_power_real=100.0, load_power_imag=50.0
            ).model_dump(),
            BusSpec(
                bus_id=4, bus_type="pq", base_kv=230.0, load_power_real=40.0, load_power_imag=5.0
            ).model_dump(),
            BusSpec(
                bus_id=5, bus_type="pq", base_kv=230.0, load_power_real=10.0, load_power_imag=6.0
            ).model_dump(),
            BusSpec(
                bus_id=6,
                bus_type="pv",
                base_kv=230.0,
                voltage_magnitude=1.0,
                generation_power_real=21.0,
                generation_power_imag=-7.0,
            ).model_dump(),
            BusSpec(
                bus_id=7,
                bus_type="pv",
                base_kv=230.0,
                voltage_magnitude=1.0,
                generation_power_real=16.0,
                generation_power_imag=-6.0,
            ).model_dump(),
            BusSpec(
                bus_id=8, bus_type="pq", base_kv=230.0, load_power_real=50.0, load_power_imag=4.0
            ).model_dump(),
            BusSpec(
                bus_id=9,
                bus_type="pv",
                base_kv=230.0,
                voltage_magnitude=1.0,
                generation_power_real=12.0,
                generation_power_imag=-5.0,
            ).model_dump(),
            BusSpec(
                bus_id=10, bus_type="pq", base_kv=230.0, load_power_real=5.0, load_power_imag=3.0
            ).model_dump(),
            BusSpec(
                bus_id=11, bus_type="pq", base_kv=230.0, load_power_real=5.0, load_power_imag=3.0
            ).model_dump(),
        ],
        "lines": [
            LineSpec(
                line_id=1, from_bus_id=1, to_bus_id=2, r1=0.0172, x1=0.0476, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=2, from_bus_id=1, to_bus_id=3, r1=0.0162, x1=0.0434, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=3, from_bus_id=2, to_bus_id=4, r1=0.0072, x1=0.0192, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=4, from_bus_id=3, to_bus_id=4, r1=0.0054, x1=0.0158, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=5, from_bus_id=2, to_bus_id=5, r1=0.0142, x1=0.0386, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=6, from_bus_id=3, to_bus_id=5, r1=0.0099, x1=0.0265, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=7, from_bus_id=4, to_bus_id=5, r1=0.0129, x1=0.0351, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=8, from_bus_id=5, to_bus_id=6, r1=0.0131, x1=0.0358, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=9, from_bus_id=5, to_bus_id=7, r1=0.0099, x1=0.0266, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=10, from_bus_id=6, to_bus_id=7, r1=0.0243, x1=0.0658, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=11, from_bus_id=6, to_bus_id=8, r1=0.0089, x1=0.0240, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=12, from_bus_id=7, to_bus_id=8, r1=0.0178, x1=0.0481, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=13, from_bus_id=7, to_bus_id=9, r1=0.0165, x1=0.0445, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=14, from_bus_id=8, to_bus_id=9, r1=0.0135, x1=0.0365, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=15, from_bus_id=8, to_bus_id=10, r1=0.0073, x1=0.0199, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=16, from_bus_id=9, to_bus_id=10, r1=0.0067, x1=0.0182, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=17, from_bus_id=6, to_bus_id=11, r1=0.0255, x1=0.0686, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=18, from_bus_id=7, to_bus_id=11, r1=0.0187, x1=0.0502, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=19, from_bus_id=10, to_bus_id=11, r1=0.0080, x1=0.0217, bshunt1=0.0
            ).model_dump(),
            LineSpec(
                line_id=20, from_bus_id=11, to_bus_id=12, r1=0.0135, x1=0.0365, bshunt1=0.0
            ).model_dump(),
        ],
        "generators": [
            GeneratorSpec(generator_id=1, bus_id=1, internal_voltage_mag=1.0).model_dump(),
            GeneratorSpec(generator_id=2, bus_id=2, internal_voltage_mag=1.0).model_dump(),
            GeneratorSpec(generator_id=3, bus_id=6, internal_voltage_mag=1.03).model_dump(),
            GeneratorSpec(generator_id=4, bus_id=7, internal_voltage_mag=1.07).model_dump(),
            GeneratorSpec(generator_id=5, bus_id=9, internal_voltage_mag=1.03).model_dump(),
        ],
        "loads": [
            LoadSpec(load_id=1, bus_id=3, p_mw=100.0, q_mvar=50.0).model_dump(),
            LoadSpec(load_id=2, bus_id=4, p_mw=40.0, q_mvar=5.0).model_dump(),
            LoadSpec(load_id=3, bus_id=5, p_mw=10.0, q_mvar=6.0).model_dump(),
            LoadSpec(load_id=4, bus_id=8, p_mw=50.0, q_mvar=4.0).model_dump(),
            LoadSpec(load_id=5, bus_id=10, p_mw=5.0, q_mvar=3.0).model_dump(),
            LoadSpec(load_id=6, bus_id=11, p_mw=5.0, q_mvar=3.0).model_dump(),
        ],
        "transformers": [],
    }


@pytest.fixture
def sample_study_request(sample_3bus_network):
    """Return a StudyRequest with a simple 3-bus network for basic testing.

    Values are dictionaries compatible with StudyRequest validation.
    """
    from core_model.specs import StudyRequest

    return StudyRequest(
        study_type="load_flow",
        system=sample_3bus_network,
        parameters={"tolerance": 1e-6, "max_iterations": 50},
    )


# Re-export fake-COM fixtures from the WP0 harness so any ETAP test module
# can request them without re-importing (avoids F811 shadowing).
from tests.test_etap_com_mocked import fake_app, project_file  # noqa: E402,F401
