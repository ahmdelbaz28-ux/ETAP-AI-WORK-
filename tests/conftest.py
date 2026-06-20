"""
Test configuration and fixtures for the Engineering Service.
Contains shared test utilities, mocks, and test network configurations.
"""

import os
import tempfile
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.bootstrap import logger
from services.study_service import Bus, Line, Load, StudyRequest, SystemSpec, Transformer
from services.study_service import Generator as Gen

# Test network configurations
TEST_NETWORKS = {
    "3-bus": {
        "buses": [
            Bus(bus_id=1, voltage_kv=20.0, bus_type="slack", angle_deg=0.0),
            Bus(bus_id=2, voltage_kv=20.0, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=3, voltage_kv=20.0, bus_type="pv", angle_deg=0.0),
        ],
        "lines": [
            Line(line_id=1, from_bus_id=1, to_bus_id=2, resistance_pu=0.02, reactance_pu=0.08, charging_siemens=0.0),
            Line(line_id=2, from_bus_id=2, to_bus_id=3, resistance_pu=0.02, reactance_pu=0.08, charging_siemens=0.0),
        ],
        "generators": [
            Gen(generator_id=1, bus_id=1, power_real_pu=1.0, power_reactive_pu=0.5, voltage_setpoint_pu=1.0),
            Gen(generator_id=2, bus_id=3, power_real_pu=0.5, power_reactive_pu=0.2, voltage_setpoint_pu=1.0),
        ],
        "loads": [
            Load(load_id=1, bus_id=2, power_real_pu=0.8, power_reactive_pu=0.6),
        ],
        "transformers": [],
    },
    "ieee-14": {
        "buses": [
            Bus(bus_id=1, voltage_kv=115.0, bus_type="slack", angle_deg=0.0),
            Bus(bus_id=2, voltage_kv=115.0, bus_type="pv", angle_deg=0.0),
            Bus(bus_id=3, voltage_kv=115.0, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=4, voltage_kv=115.0, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=5, voltage_kv=115.0, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=6, voltage_kv=13.8, bus_type="pv", angle_deg=0.0),
            Bus(bus_id=7, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=8, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=9, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=10, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=11, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=12, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=13, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
            Bus(bus_id=14, voltage_kv=13.8, bus_type="pq", angle_deg=0.0),
        ],
        "lines": [
            Line(line_id=1, from_bus_id=1, to_bus_id=2, resistance_pu=0.01938, reactance_pu=0.05917, charging_siemens=0.0528),
            Line(line_id=2, from_bus_id=1, to_bus_id=5, resistance_pu=0.05403, reactance_pu=0.22304, charging_siemens=0.0492),
            Line(line_id=3, from_bus_id=2, to_bus_id=3, resistance_pu=0.04699, reactance_pu=0.19797, charging_siemens=0.0438),
            Line(line_id=4, from_bus_id=2, to_bus_id=4, resistance_pu=0.05811, reactance_pu=0.17632, charging_siemens=0.0340),
            Line(line_id=5, from_bus_id=2, to_bus_id=5, resistance_pu=0.05695, reactance_pu=0.21982, charging_siemens=0.0346),
            Line(line_id=6, from_bus_id=3, to_bus_id=4, resistance_pu=0.06701, reactance_pu=0.17103, charging_siemens=0.0128),
            Line(line_id=7, from_bus_id=4, to_bus_id=5, resistance_pu=0.01335, reactance_pu=0.04211, charging_siemens=0.0),
            Line(line_id=8, from_bus_id=4, to_bus_id=7, resistance_pu=0.0, reactance_pu=0.20912, charging_siemens=0.0),
            Line(line_id=9, from_bus_id=4, to_bus_id=9, resistance_pu=0.0, reactance_pu=0.55618, charging_siemens=0.0),
            Line(line_id=10, from_bus_id=5, to_bus_id=6, resistance_pu=0.0, reactance_pu=0.25202, charging_siemens=0.0),
            Line(line_id=11, from_bus_id=6, to_bus_id=11, resistance_pu=0.09498, reactance_pu=0.19890, charging_siemens=0.0),
            Line(line_id=12, from_bus_id=6, to_bus_id=12, resistance_pu=0.12291, reactance_pu=0.25581, charging_siemens=0.0),
            Line(line_id=13, from_bus_id=6, to_bus_id=13, resistance_pu=0.06615, reactance_pu=0.13027, charging_siemens=0.0),
            Line(line_id=14, from_bus_id=7, to_bus_id=8, resistance_pu=0.0, reactance_pu=0.17615, charging_siemens=0.0),
            Line(line_id=15, from_bus_id=7, to_bus_id=9, resistance_pu=0.0, reactance_pu=0.11001, charging_siemens=0.0),
            Line(line_id=16, from_bus_id=9, to_bus_id=10, resistance_pu=0.03181, reactance_pu=0.08450, charging_siemens=0.0),
            Line(line_id=17, from_bus_id=9, to_bus_id=14, resistance_pu=0.12711, reactance_pu=0.27038, charging_siemens=0.0),
            Line(line_id=18, from_bus_id=10, to_bus_id=11, resistance_pu=0.08205, reactance_pu=0.19207, charging_siemens=0.0),
            Line(line_id=19, from_bus_id=12, to_bus_id=13, resistance_pu=0.22092, reactance_pu=0.19988, charging_siemens=0.0),
            Line(line_id=20, from_bus_id=13, to_bus_id=14, resistance_pu=0.17093, reactance_pu=0.34802, charging_siemens=0.0),
        ],
        "generators": [
            Gen(generator_id=1, bus_id=1, power_real_pu=0.0000, power_reactive_pu=0.0000, voltage_setpoint_pu=1.0600),
            Gen(generator_id=2, bus_id=2, power_real_pu=0.4000, power_reactive_pu=0.0000, voltage_setpoint_pu=1.0450),
            Gen(generator_id=3, bus_id=3, power_real_pu=0.0000, power_reactive_pu=0.0000, voltage_setpoint_pu=1.0100),
            Gen(generator_id=4, bus_id=6, power_real_pu=0.0000, power_reactive_pu=0.0000, voltage_setpoint_pu=1.0700),
            Gen(generator_id=5, bus_id=8, power_real_pu=0.0000, power_reactive_pu=0.0000, voltage_setpoint_pu=1.0900),
        ],
        "loads": [
            Load(load_id=1, bus_id=2, power_real_pu=0.2170, power_reactive_pu=0.1270),
            Load(load_id=2, bus_id=3, power_real_pu=0.9420, power_reactive_pu=0.1900),
            Load(load_id=3, bus_id=4, power_real_pu=0.4780, power_reactive_pu=0.0390),
            Load(load_id=4, bus_id=5, power_real_pu=0.0760, power_reactive_pu=0.0160),
            Load(load_id=5, bus_id=6, power_real_pu=0.1120, power_reactive_pu=0.0750),
            Load(load_id=6, bus_id=9, power_real_pu=0.2950, power_reactive_pu=0.1660),
            Load(load_id=7, bus_id=10, power_real_pu=0.0900, power_reactive_pu=0.0580),
            Load(load_id=8, bus_id=11, power_real_pu=0.0350, power_reactive_pu=0.0180),
            Load(load_id=9, bus_id=12, power_real_pu=0.0610, power_reactive_pu=0.0160),
            Load(load_id=10, bus_id=13, power_real_pu=0.1350, power_reactive_pu=0.0580),
            Load(load_id=11, bus_id=14, power_real_pu=0.1490, power_reactive_pu=0.0500),
        ],
        "transformers": [],
    }
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
        parameters={"tolerance": 1e-6, "max_iterations": 50}
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
    logger.setLevel("DEBUG")

    yield

    # Clean up environment variables after tests
    if "ENGINEERING_SERVICE_AUTH_DISABLED" in os.environ:
        del os.environ["ENGINEERING_SERVICE_AUTH_DISABLED"]
    if "USE_ETAP" in os.environ:
        del os.environ["USE_ETAP"]
    if "PRIVACY_MODE" in os.environ:
        del os.environ["PRIVACY_MODE"]
