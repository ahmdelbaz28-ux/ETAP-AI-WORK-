"""
Unit tests for etap_integration/etap_adapter.py.
Covers: factory, MockETAPAdapter, ETAPProviderAdapter, disabled/enabled paths.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from etap_integration.etap_adapter import (
    ETAPAdapter,
    ETAPProviderAdapter,
    ETAPResult,
    ETAPStudyType,
    MockETAPAdapter,
    get_etap_adapter,
)

# ─── ETAPStudyType enum ─────────────────────────────────────────────────────

class TestETAPStudyType:
    def test_all_study_types_exist(self):
        expected = {
            "LOAD_FLOW", "SHORT_CIRCUIT", "ARC_FLASH",
            "HARMONIC_ANALYSIS", "OPTIMAL_POWER_FLOW",
            "MOTOR_STARTING", "PROTECTION_COORDINATION",
        }
        actual = {e.name for e in ETAPStudyType}
        assert expected == actual

    def test_values_are_snake_case(self):
        for member in ETAPStudyType:
            assert member.value == member.value.lower()
            assert " " not in member.value


# ─── ETAPResult ─────────────────────────────────────────────────────────────

class TestETAPResult:
    def test_defaults(self):
        r = ETAPResult(success=True, data={"v": 1})
        assert r.success is True
        assert r.data == {"v": 1}
        assert r.warnings == []
        assert r.errors == []
        assert r.execution_time == 0.0

    def test_with_errors_and_warnings(self):
        r = ETAPResult(
            success=False,
            data={},
            warnings=["W1"],
            errors=["E1"],
            execution_time=1.5,
        )
        assert r.warnings == ["W1"]
        assert r.errors == ["E1"]
        assert r.execution_time == 1.5


# ─── MockETAPAdapter ────────────────────────────────────────────────────────

class TestMockETAPAdapter:
    def test_disabled_when_use_etap_false(self):
        with patch.dict(os.environ, {"USE_ETAP": "false"}):
            adapter = MockETAPAdapter()
            assert adapter.is_available() is False

    def test_enabled_when_use_etap_true(self):
        with patch.dict(os.environ, {"USE_ETAP": "true"}):
            adapter = MockETAPAdapter()
            assert adapter.is_available() is True

    def test_execute_study_disabled_returns_error(self):
        with patch.dict(os.environ, {"USE_ETAP": "false"}):
            adapter = MockETAPAdapter()
            result = adapter.execute_study("/fake.etap", ETAPStudyType.LOAD_FLOW)
            assert result.success is False
            assert any("disabled" in e.lower() for e in result.errors)

    def test_execute_study_enabled_returns_mock_data(self):
        with patch.dict(os.environ, {"USE_ETAP": "true"}):
            adapter = MockETAPAdapter()
            result = adapter.execute_study(
                "/project.etap",
                ETAPStudyType.SHORT_CIRCUIT,
                parameters={"bus_id": 1},
            )
            assert result.success is True
            assert result.data["study_type"] == "short_circuit"
            assert result.data["project_path"] == "/project.etap"
            assert "parameters_used" in result.data
            assert result.data["parameters_used"]["bus_id"] == 1
            assert len(result.warnings) > 0  # mock warning

    def test_execute_study_no_parameters(self):
        with patch.dict(os.environ, {"USE_ETAP": "true"}):
            adapter = MockETAPAdapter()
            result = adapter.execute_study("/p.etap", ETAPStudyType.ARC_FLASH)
            assert result.success is True
            assert "parameters_used" not in result.data


# ─── ETAPProviderAdapter ────────────────────────────────────────────────────

class TestETAPProviderAdapter:
    def test_disabled_when_use_etap_false(self):
        with patch.dict(os.environ, {"USE_ETAP": "false"}):
            adapter = ETAPProviderAdapter()
            assert adapter.is_available() is False

    def test_execute_study_disabled_returns_error(self):
        with patch.dict(os.environ, {"USE_ETAP": "false"}):
            adapter = ETAPProviderAdapter()
            result = adapter.execute_study("/fake.etap", ETAPStudyType.LOAD_FLOW)
            assert result.success is False

    def test_execute_study_unavailable_returns_error(self):
        with patch.dict(os.environ, {"USE_ETAP": "true"}):
            adapter = ETAPProviderAdapter()
            # Force unavailable
            adapter._available = False
            result = adapter.execute_study("/fake.etap", ETAPStudyType.LOAD_FLOW)
            assert result.success is False
            assert any("not available" in e.lower() for e in result.errors)

    @patch.dict(os.environ, {"USE_ETAP": "true"})
    def test_execute_study_provider_exception(self):
        adapter = ETAPProviderAdapter()
        adapter._available = True
        adapter._provider = MagicMock()
        adapter._provider.execute_study.side_effect = RuntimeError("COM crash")

        result = adapter.execute_study("/p.etap", ETAPStudyType.LOAD_FLOW)
        assert result.success is False
        assert any("COM crash" in e for e in result.errors)


# ─── Factory function ───────────────────────────────────────────────────────

class TestGetEtapAdapter:
    def test_returns_mock_when_use_mock(self):
        with patch.dict(os.environ, {"USE_MOCK_ETAP": "true"}):
            adapter = get_etap_adapter()
            assert isinstance(adapter, MockETAPAdapter)

    def test_returns_provider_adapter_by_default(self):
        with patch.dict(os.environ, {"USE_MOCK_ETAP": "false"}, clear=False):
            adapter = get_etap_adapter()
            assert isinstance(adapter, ETAPProviderAdapter)
