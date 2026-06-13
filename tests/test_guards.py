"""
Tests for the Guards Module
=============================
Validates the guard-skills integration: AI failure mode detection,
code guard, test guard, and docs guard.
"""

import pytest
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guards.base import GuardSeverity, GuardMode, GuardViolation, GuardResult, BaseGuard
from guards.ai_failure_modes import AIFailureModeDetector, AI_FAILURE_MODES
from guards.code_guard import CodeGuard
from guards.test_guard import TestGuard
from guards.docs_guard import DocsGuard


# ============================================================================
# Base Guard Tests
# ============================================================================

class TestGuardSeverity:
    def test_severity_values(self):
        assert GuardSeverity.MUST_FIX.value == "must_fix"
        assert GuardSeverity.SHOULD_FIX.value == "should_fix"
        assert GuardSeverity.WORTH_NOTING.value == "worth_noting"


class TestGuardResult:
    def test_passed_with_no_violations(self):
        result = GuardResult(guard_name="test", mode=GuardMode.GUARD_PASS)
        assert result.passed is True
        assert result.must_fix_count == 0

    def test_failed_with_must_fix(self):
        result = GuardResult(
            guard_name="test",
            mode=GuardMode.GUARD_PASS,
            violations=[
                GuardViolation(
                    rule_id="T-01", rule_name="test",
                    severity=GuardSeverity.MUST_FIX,
                    description="must fix violation"
                )
            ]
        )
        assert result.passed is False
        assert result.must_fix_count == 1

    def test_passed_with_should_fix_only(self):
        result = GuardResult(
            guard_name="test",
            mode=GuardMode.GUARD_PASS,
            violations=[
                GuardViolation(
                    rule_id="T-01", rule_name="test",
                    severity=GuardSeverity.SHOULD_FIX,
                    description="should fix violation"
                )
            ]
        )
        assert result.passed is True
        assert result.should_fix_count == 1

    def test_to_dict_serialization(self):
        result = GuardResult(
            guard_name="test",
            mode=GuardMode.GUARD_PASS,
            violations=[
                GuardViolation(
                    rule_id="FM-01", rule_name="Catch-all",
                    severity=GuardSeverity.MUST_FIX,
                    description="test"
                )
            ],
            metadata={"key": "value"}
        )
        d = result.to_dict()
        assert d["guard_name"] == "test"
        assert d["passed"] is False
        assert d["must_fix"] == 1
        assert len(d["violations"]) == 1
        assert d["violations"][0]["rule_id"] == "FM-01"


# ============================================================================
# AI Failure Mode Detector Tests
# ============================================================================

class TestAIFailureModeDetector:
    """Test the 14 AI failure mode detectors."""

    def setup_method(self):
        self.detector = AIFailureModeDetector()

    def test_14_failure_modes_defined(self):
        assert len(AI_FAILURE_MODES) == 14

    def test_clean_code_passes(self):
        clean_code = '''
def calculate_power(voltage: float, current: float) -> float:
    """Calculate electrical power."""
    return voltage * current
'''
        result = self.detector.detect(clean_code)
        assert result.passed is True

    def test_fm01_catch_all_bare_except(self):
        bad_code = '''
try:
    result = compute()
except:
    pass
'''
        result = self.detector.detect(bad_code)
        fm01_violations = [v for v in result.violations if v.rule_id == "FM-01"]
        assert len(fm01_violations) > 0
        assert result.passed is False

    def test_fm01_broad_exception_swallowing(self):
        bad_code = '''
try:
    result = compute()
except Exception:
    pass
'''
        result = self.detector.detect(bad_code)
        fm01_violations = [v for v in result.violations if v.rule_id == "FM-01"]
        assert len(fm01_violations) > 0

    def test_fm01_specific_exception_passes(self):
        good_code = '''
try:
    result = compute()
except ValueError as e:
    logger.error("Invalid value: %s", e)
    raise
'''
        result = self.detector.detect(good_code)
        fm01_violations = [v for v in result.violations if v.rule_id == "FM-01"]
        assert len(fm01_violations) == 0

    def test_fm04_hardcoded_success_return(self):
        bad_code = '''
def validate_system(data):
    return True
'''
        result = self.detector.detect(bad_code)
        fm04_violations = [v for v in result.violations if v.rule_id == "FM-04"]
        assert len(fm04_violations) > 0

    def test_fm04_derived_return_passes(self):
        good_code = '''
def validate_system(data):
    result = compute_validation(data)
    return result.is_valid
'''
        result = self.detector.detect(good_code)
        fm04_violations = [v for v in result.violations if v.rule_id == "FM-04"]
        assert len(fm04_violations) == 0

    def test_fm07_unused_imports(self):
        bad_code = '''
import os
import json
import re

def compute():
    return 42
'''
        result = self.detector.detect(bad_code)
        fm07_violations = [v for v in result.violations if v.rule_id == "FM-07"]
        assert len(fm07_violations) > 0

    def test_fm08_write_before_read(self):
        bad_code = '''
def process(data):
    data = transform(data)
    return data
'''
        result = self.detector.detect(bad_code)
        fm08_violations = [v for v in result.violations if v.rule_id == "FM-08"]
        assert len(fm08_violations) > 0

    def test_fm13_magic_numbers(self):
        bad_code = '''
def calculate_fault_current(voltage):
    return voltage / 0.457
'''
        result = self.detector.detect(bad_code)
        fm13_violations = [v for v in result.violations if v.rule_id == "FM-13"]
        assert len(fm13_violations) > 0

    def test_regex_fallback_on_invalid_python(self):
        # Code with syntax error should still run via regex fallback
        bad_code = 'try:\n  x = 1\nexcept:\n  pass'
        result = self.detector.detect(bad_code)
        # Should not crash, may or may not find violations via regex
        assert isinstance(result, GuardResult)


# ============================================================================
# Code Guard Tests
# ============================================================================

class TestCodeGuard:
    def setup_method(self):
        self.guard = CodeGuard()

    def test_clean_code_passes(self):
        clean_code = '''
def calculate_impedance(voltage: float, current: float) -> complex:
    """Calculate impedance from voltage and current."""
    if current == 0:
        raise ValueError("Current cannot be zero")
    return voltage / current
'''
        result = self.guard.scan(clean_code)
        # Should not have MUST_FIX violations
        assert result.must_fix_count == 0

    def test_long_function_detected(self):
        long_code = '''
def very_long_function(data):
    """A function that is way too long."""
    x = 1
    y = 2
    z = 3
    a = 4
    b = 5
    c = 6
    d = 7
    e = 8
    f = 9
    g = 10
    h = 11
    i = 12
    j = 13
    k = 14
    l = 15
    m = 16
    n = 17
    o = 18
    p = 19
    q = 20
    r = 21
    return x + y + z
'''
        result = self.guard.scan(long_code)
        cc01_violations = [v for v in result.violations if v.rule_id == "CC-01"]
        assert len(cc01_violations) > 0

    def test_too_many_parameters(self):
        bad_code = '''
def process(a, b, c, d, e, f, g, h):
    return a + b
'''
        result = self.guard.scan(bad_code)
        cc02_violations = [v for v in result.violations if v.rule_id == "CC-02"]
        assert len(cc02_violations) > 0

    def test_high_complexity(self):
        complex_code = '''
def complex_function(x):
    if x > 0:
        if x > 10:
            if x > 20:
                if x > 30:
                    if x > 40:
                        if x > 50:
                            if x > 60:
                                if x > 70:
                                    if x > 80:
                                        if x > 90:
                                            return 1
                                        return 2
                                    return 3
                                return 4
                            return 5
                        return 6
                    return 7
                return 8
            return 9
        return 10
    return 11
'''
        result = self.guard.scan(complex_code)
        cc17_violations = [v for v in result.violations if v.rule_id == "CC-17"]
        assert len(cc17_violations) > 0


# ============================================================================
# Test Guard Tests
# ============================================================================

class TestTestGuard:
    def setup_method(self):
        self.guard = TestGuard()

    def test_clean_test_passes(self):
        clean_test = '''
def test_load_flow_converges_with_valid_system():
    """Test that load flow converges with a valid power system."""
    system = create_test_system()
    result = engine.run_load_flow(system)
    assert result.converged is True
'''
        result = self.guard.scan(clean_test)
        # Should not have MUST_FIX violations
        assert result.must_fix_count == 0

    def test_mock_assert_detected(self):
        bad_test = '''
def test_agent_calls_tool():
    mock_tool = MagicMock()
    agent.run()
    mock_tool.assert_called_with("expected_arg")
'''
        result = self.guard.scan(bad_test)
        fm14_violations = [v for v in result.violations if v.rule_id == "FM-14"]
        assert len(fm14_violations) > 0

    def test_poor_test_naming(self):
        bad_test = '''
def test_1():
    assert True
'''
        result = self.guard.scan(bad_test)
        t05_violations = [v for v in result.violations if v.rule_id == "T-05"]
        assert len(t05_violations) > 0

    def test_llm_exact_string_assertion(self):
        bad_test = '''
def test_llm_response():
    response = llm.generate("hello")
    assert response == "Hello, how can I help you?"
'''
        result = self.guard.scan(bad_test)
        tl1_violations = [v for v in result.violations if v.rule_id == "T-L1"]
        assert len(tl1_violations) > 0


# ============================================================================
# Docs Guard Tests
# ============================================================================

class TestDocsGuard:
    def setup_method(self):
        self.guard = DocsGuard()

    def test_clean_docs_pass(self):
        clean_docs = '''
# Power System Analysis

The `PowerSystemEngine` class provides load flow analysis.

## Installation

Requires Python 3.10+ and numpy 1.24+.
'''
        result = self.guard.scan(clean_docs)
        assert result.must_fix_count == 0

    def test_unverifiable_claims_detected(self):
        bad_docs = '''
# Our Engine

It is well-known that our engine is the fastest solution available.
Everyone knows that Newton-Raphson always converges.
'''
        result = self.guard.scan(bad_docs)
        d04_violations = [v for v in result.violations if v.rule_id == "D-04"]
        assert len(d04_violations) > 0

    def test_filler_phrases_detected(self):
        bad_docs = '''
# Overview

In this section, we will discuss the load flow analysis.
It is important to note that voltage matters.
'''
        result = self.guard.scan(bad_docs)
        d07_violations = [v for v in result.violations if v.rule_id == "D-07"]
        assert len(d07_violations) > 0

    def test_vague_version_detected(self):
        bad_docs = '''
# Installation

Install the latest version of numpy for best results.
'''
        result = self.guard.scan(bad_docs)
        d05_violations = [v for v in result.violations if v.rule_id == "D-05"]
        assert len(d05_violations) > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestGuardIntegration:
    """Test that guards integrate correctly with the ETAP platform."""

    def test_guard_imports(self):
        """All guard classes should be importable from the guards package."""
        from guards import (
            GuardSeverity, GuardViolation, GuardResult,
            BaseGuard, GuardMode,
            AIFailureModeDetector, AI_FAILURE_MODES,
            CodeGuard, TestGuard, DocsGuard,
        )

    def test_failure_modes_have_research_sources(self):
        """Every AI failure mode should cite its research source."""
        for fm in AI_FAILURE_MODES:
            assert fm.research_source, f"FM {fm.id} has no research source"
            assert fm.id.startswith("FM-"), f"Invalid ID format: {fm.id}"

    def test_failure_mode_ids_sequential(self):
        """Failure mode IDs should be FM-01 through FM-14."""
        ids = sorted([fm.id for fm in AI_FAILURE_MODES])
        expected = [f"FM-{i:02d}" for i in range(1, 15)]
        assert ids == expected

    def test_code_guard_includes_ai_failure_modes(self):
        """CodeGuard should include AI failure mode violations."""
        guard = CodeGuard()
        bad_code = '''
try:
    result = compute()
except:
    pass
'''
        result = guard.scan(bad_code)
        fm_violations = [v for v in result.violations if v.rule_id.startswith("FM-")]
        assert len(fm_violations) > 0

    def test_engineering_code_quality(self):
        """Test that well-structured engineering code passes the guard."""
        good_code = '''
from dataclasses import dataclass
from typing import Optional

IMPEDANCE_BASE = 100.0  # Base MVA for per-unit system


@dataclass
class BusResult:
    """Load flow result for a single bus."""
    bus_id: int
    voltage_magnitude: float
    voltage_angle: float

    @property
    def is_within_limits(self) -> bool:
        """Check if voltage is within IEEE 3002.7 limits (0.95-1.05 pu)."""
        return 0.95 <= self.voltage_magnitude <= 1.05


def calculate_bus_impedance(voltage: float, current: complex) -> complex:
    """Calculate bus impedance from voltage and current phasors.

    Uses Ohm's law: Z = V / I

    Args:
        voltage: Voltage magnitude in per-unit.
        current: Current phasor in per-unit.

    Returns:
        Impedance as a complex number in per-unit.

    Raises:
        ValueError: If current is zero (open circuit).
    """
    if abs(current) < 1e-10:
        raise ValueError("Current is zero — open circuit condition")
    return complex(voltage, 0) / current
'''
        result = CodeGuard().scan(good_code)
        # Well-structured code should have minimal MUST_FIX violations
        assert result.must_fix_count == 0, \
            f"Expected no MUST_FIX violations, got: {[v.rule_id for v in result.violations if v.severity == GuardSeverity.MUST_FIX]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
