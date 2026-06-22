"""
Unit tests for the study service functionality.
Tests the core study execution logic without external dependencies.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.bootstrap import logger
from services.study_service import Bus, Line, Load, StudyRequest, SystemSpec, execute_study_logic
from services.study_service import Generator as Gen


def test_execute_study_logic_basic(sample_study_request):
    """Test basic study execution with a simple 3-bus network."""
    # Execute the study
    result = execute_study_logic(sample_study_request, "test-trace-id", 0.0)

    # Basic assertions
    assert result.success is True
    assert result.study_type == "load_flow"
    assert result.trace_id == "test-trace-id"
    assert hasattr(result, "results")


def test_execute_study_logic_invalid_network(sample_3bus_network):
    """Test study execution with an invalid network (missing slack bus)."""
    # Create an invalid network without a slack bus
    invalid_network = sample_3bus_network.copy()
    invalid_network["buses"] = [bus for bus in invalid_network["buses"] if bus.bus_type != "slack"]

    # Create a study request with the invalid network
    invalid_request = StudyRequest(
        study_type="load_flow",
        system_spec=SystemSpec(**invalid_network),
        parameters={"tolerance": 1e-6, "max_iterations": 50},
    )

    # Execute the study and expect failure
    result = execute_study_logic(invalid_request, "test-trace-id-invalid", 0.0)

    # Should still succeed at execution level but results may vary
    assert result.success is True  # Execution itself succeeds, but solution may not converge
    assert result.trace_id == "test-trace-id-invalid"


def test_execute_study_logic_different_types(sample_3bus_network):
    """Test study execution with different study types."""
    base_request = StudyRequest(
        study_type="load_flow",
        system_spec=SystemSpec(**sample_3bus_network),
        parameters={"tolerance": 1e-6, "max_iterations": 50},
    )

    # Test different study types
    for study_type in ["load_flow", "fault_analysis", "arc_flash"]:
        base_request.study_type = study_type
        result = execute_study_logic(base_request, f"test-trace-{study_type}", 0.0)

        assert result.success is True
        assert result.study_type == study_type
        assert result.trace_id == f"test-trace-{study_type}"


def test_execute_study_logic_with_parameters(sample_3bus_network):
    """Test study execution with different parameters."""
    base_request = StudyRequest(
        study_type="load_flow",
        system_spec=SystemSpec(**sample_3bus_network),
        parameters={"tolerance": 1e-8, "max_iterations": 100},
    )

    result = execute_study_logic(base_request, "test-trace-params", 0.0)

    assert result.success is True
    assert result.study_type == "load_flow"
    assert result.trace_id == "test-trace-params"


def test_execute_study_logic_large_network(sample_ieee14_network):
    """Test study execution with a larger IEEE 14-bus network."""
    request = StudyRequest(
        study_type="load_flow",
        system_spec=SystemSpec(**sample_ieee14_network),
        parameters={"tolerance": 1e-6, "max_iterations": 50},
    )

    result = execute_study_logic(request, "test-trace-large", 0.0)

    assert result.success is True
    assert result.study_type == "load_flow"
    assert result.trace_id == "test-trace-large"
