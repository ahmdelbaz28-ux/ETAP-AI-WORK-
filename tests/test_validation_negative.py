"""Negative tests for core_model/specs.py validators.

These tests verify that validators REJECT invalid data — not just that
they accept valid data (which the existing engineering tests cover).

Each test sends data that should be rejected and asserts that a
ValidationError is raised.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestLineSpecValidation:
    """Negative tests for LineSpec validators."""

    def test_self_loop_rejected(self):
        """Line from bus to itself must be rejected (matrix singularity)."""
        from core_model.specs import LineSpec
        with pytest.raises(ValidationError, match="self-loop"):
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=1)

    def test_negative_reactance_rejected(self):
        """Negative reactance is non-physical."""
        from core_model.specs import LineSpec
        with pytest.raises(ValidationError, match="non-negative"):
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, x1=-0.1)

    def test_negative_rating_rejected(self):
        """Zero or negative rating is non-physical."""
        from core_model.specs import LineSpec
        with pytest.raises(ValidationError, match="positive"):
            LineSpec(line_id=1, from_bus_id=1, to_bus_id=2, rating_mva=0)


class TestTransformerSpecValidation:
    """Negative tests for TransformerSpec validators."""

    def test_zero_reactance_rejected(self):
        """Zero x1 causes division by zero in short-circuit."""
        from core_model.specs import TransformerSpec
        with pytest.raises(ValidationError, match="positive"):
            TransformerSpec(transformer_id=1, from_bus_id=1, to_bus_id=2, x1=0)

    def test_self_loop_rejected(self):
        """Transformer from bus to itself is invalid."""
        from core_model.specs import TransformerSpec
        with pytest.raises(ValidationError, match="from_bus_id"):
            TransformerSpec(transformer_id=1, from_bus_id=1, to_bus_id=1)

    def test_invalid_tap_ratio_rejected(self):
        """Tap ratio outside 0.5-2.0 is non-physical."""
        from core_model.specs import TransformerSpec
        with pytest.raises(ValidationError, match="tap_ratio"):
            TransformerSpec(transformer_id=1, from_bus_id=1, to_bus_id=2, tap_ratio=3.0)


class TestGeneratorSpecValidation:
    """Negative tests for GeneratorSpec validators."""

    def test_zero_reactance_rejected(self):
        """Zero x1 causes division by zero in fault analysis."""
        from core_model.specs import GeneratorSpec
        with pytest.raises(ValidationError, match="positive"):
            GeneratorSpec(generator_id=1, bus_id=1, x1=0)

    def test_extreme_voltage_rejected(self):
        """Voltage magnitude outside 0.5-1.5 pu indicates data error."""
        from core_model.specs import GeneratorSpec
        with pytest.raises(ValidationError, match="voltage_mag"):
            GeneratorSpec(generator_id=1, bus_id=1, internal_voltage_mag=5.0)


class TestLoadSpecValidation:
    """Negative tests for LoadSpec validators."""

    def test_nan_power_rejected(self):
        """NaN power values cause NaN propagation."""
        from core_model.specs import LoadSpec
        import math
        with pytest.raises(ValidationError, match="finite"):
            LoadSpec(load_id=1, bus_id=1, p_mw=math.nan)

    def test_extreme_power_rejected(self):
        """Power > 1e6 MW is unreasonable (prevents overflow)."""
        from core_model.specs import LoadSpec
        with pytest.raises(ValidationError, match="unreasonably large"):
            LoadSpec(load_id=1, bus_id=1, p_mw=1e7)


class TestSystemSpecValidation:
    """Negative tests for SystemSpec validators."""

    def test_too_many_buses_rejected(self):
        """> 10000 buses is likely malicious (OOM prevention)."""
        from core_model.specs import SystemSpec, BusSpec
        buses = [BusSpec(bus_id=i, voltage_kv=13.8) for i in range(10001)]
        with pytest.raises(ValidationError, match="10000"):
            SystemSpec(buses=buses)

    def test_zero_base_mva_rejected(self):
        """Base MVA must be positive."""
        from core_model.specs import SystemSpec
        with pytest.raises(ValidationError, match="positive"):
            SystemSpec(base_mva=0)


class TestStudyRequestValidation:
    """Negative tests for StudyRequest validators."""

    def test_too_many_parameters_rejected(self):
        """> 100 parameter keys is likely malicious (OOM prevention)."""
        from core_model.specs import StudyRequest
        params = {f"key_{i}": "value" for i in range(101)}
        with pytest.raises(ValidationError, match="100"):
            StudyRequest(study_type="load_flow", parameters=params)

    def test_path_traversal_rejected(self):
        """etap_project_path with .. must be rejected."""
        from core_model.specs import StudyRequest
        with pytest.raises(ValidationError, match="traversal"):
            StudyRequest(study_type="load_flow", etap_project_path="../../etc/passwd")

    def test_unix_absolute_path_rejected(self):
        """etap_project_path starting with / must be rejected."""
        from core_model.specs import StudyRequest
        with pytest.raises(ValidationError, match="start with '/'"):
            StudyRequest(study_type="load_flow", etap_project_path="/etc/passwd")

    def test_windows_path_accepted(self):
        """Windows-style paths (C:\\...) must be accepted."""
        from core_model.specs import StudyRequest
        # Should NOT raise
        req = StudyRequest(study_type="load_flow", etap_project_path="C:\\Projects\\test.etap")
        assert req.etap_project_path == "C:\\Projects\\test.etap"

    def test_invalid_study_type_rejected(self):
        """Invalid study type must be rejected."""
        from core_model.specs import StudyRequest
        with pytest.raises(ValidationError, match="study_type"):
            StudyRequest(study_type="invalid_study")
