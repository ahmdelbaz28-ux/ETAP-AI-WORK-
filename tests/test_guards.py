"""
Comprehensive Tests for the Guards Module Integration
========================================================
Tests the guard-skills integration with real ETAP engineering code patterns.
Validates: AI failure modes, code guard, test guard, docs guard,
secure executor integration, and orchestrator integration.
"""

import sys
import os
import json
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from guards.base import GuardSeverity, GuardMode, GuardViolation, GuardResult, BaseGuard
from guards.ai_failure_modes import AIFailureModeDetector, AI_FAILURE_MODES
from guards.code_guard import CodeGuard
from guards.test_guard import TestGuard
from guards.docs_guard import DocsGuard


# ============================================================================
# Test 1: Base Guard Framework
# ============================================================================

def test_severity_values():
    assert GuardSeverity.MUST_FIX.value == "must_fix"
    assert GuardSeverity.SHOULD_FIX.value == "should_fix"
    assert GuardSeverity.WORTH_NOTING.value == "worth_noting"
    print("PASS: test_severity_values")


def test_guard_result_passed():
    result = GuardResult(guard_name="test", mode=GuardMode.GUARD_PASS)
    assert result.passed is True
    assert result.must_fix_count == 0
    print("PASS: test_guard_result_passed")


def test_guard_result_failed():
    result = GuardResult(
        guard_name="test", mode=GuardMode.GUARD_PASS,
        violations=[GuardViolation(rule_id="FM-01", rule_name="test",
                                   severity=GuardSeverity.MUST_FIX, description="must fix")]
    )
    assert result.passed is False
    assert result.must_fix_count == 1
    print("PASS: test_guard_result_failed")


def test_guard_result_should_fix_still_passes():
    result = GuardResult(
        guard_name="test", mode=GuardMode.GUARD_PASS,
        violations=[GuardViolation(rule_id="CC-01", rule_name="test",
                                   severity=GuardSeverity.SHOULD_FIX, description="should fix")]
    )
    assert result.passed is True  # SHOULD_FIX doesn't block
    assert result.should_fix_count == 1
    print("PASS: test_guard_result_should_fix_still_passes")


def test_to_dict_serialization():
    result = GuardResult(
        guard_name="test", mode=GuardMode.GUARD_PASS,
        violations=[GuardViolation(rule_id="FM-01", rule_name="Catch-all",
                                   severity=GuardSeverity.MUST_FIX, description="test")],
        metadata={"key": "value"}
    )
    d = result.to_dict()
    assert d["guard_name"] == "test"
    assert d["passed"] is False
    assert d["must_fix"] == 1
    assert len(d["violations"]) == 1
    assert d["violations"][0]["rule_id"] == "FM-01"
    print("PASS: test_to_dict_serialization")


# ============================================================================
# Test 2: AI Failure Mode Detection (14 modes)
# ============================================================================

def test_14_failure_modes_defined():
    assert len(AI_FAILURE_MODES) == 14, f"Expected 14, got {len(AI_FAILURE_MODES)}"
    ids = sorted([fm.id for fm in AI_FAILURE_MODES])
    expected = [f"FM-{i:02d}" for i in range(1, 15)]
    assert ids == expected, f"IDs mismatch: {ids}"
    # Every failure mode should cite research
    for fm in AI_FAILURE_MODES:
        assert fm.research_source, f"FM {fm.id} has no research source"
    print("PASS: test_14_failure_modes_defined")


def test_fm01_catch_all_bare_except():
    detector = AIFailureModeDetector()
    bad_code = 'try:\n    result = compute()\nexcept:\n    pass'
    result = detector.detect(bad_code)
    fm01 = [v for v in result.violations if v.rule_id == "FM-01"]
    assert len(fm01) > 0, "FM-01 not detected for bare except"
    assert result.passed is False
    print("PASS: test_fm01_catch_all_bare_except")


def test_fm01_broad_exception_swallowing():
    detector = AIFailureModeDetector()
    bad_code = 'try:\n    result = compute()\nexcept Exception:\n    pass'
    result = detector.detect(bad_code)
    fm01 = [v for v in result.violations if v.rule_id == "FM-01"]
    assert len(fm01) > 0, "FM-01 not detected for broad Exception pass"
    print("PASS: test_fm01_broad_exception_swallowing")


def test_fm01_specific_exception_passes():
    detector = AIFailureModeDetector()
    good_code = '''
try:
    result = compute()
except ValueError as e:
    logger.error("Invalid value: %s", e)
    raise
'''
    result = detector.detect(good_code)
    fm01 = [v for v in result.violations if v.rule_id == "FM-01"]
    assert len(fm01) == 0, f"FM-01 false positive on specific exception: {fm01}"
    print("PASS: test_fm01_specific_exception_passes")


def test_fm04_hardcoded_success_return():
    detector = AIFailureModeDetector()
    bad_code = 'def validate_system(data):\n    return True'
    result = detector.detect(bad_code)
    fm04 = [v for v in result.violations if v.rule_id == "FM-04"]
    assert len(fm04) > 0, "FM-04 not detected for hardcoded True return"
    print("PASS: test_fm04_hardcoded_success_return")


def test_fm04_derived_return_passes():
    detector = AIFailureModeDetector()
    good_code = 'def validate_system(data):\n    result = compute_validation(data)\n    return result.is_valid'
    result = detector.detect(good_code)
    fm04 = [v for v in result.violations if v.rule_id == "FM-04"]
    assert len(fm04) == 0, f"FM-04 false positive on derived return: {fm04}"
    print("PASS: test_fm04_derived_return_passes")


def test_fm07_unused_imports():
    detector = AIFailureModeDetector()
    bad_code = 'import os\nimport json\nimport re\n\ndef compute():\n    return 42'
    result = detector.detect(bad_code)
    fm07 = [v for v in result.violations if v.rule_id == "FM-07"]
    assert len(fm07) > 0, "FM-07 not detected for unused imports"
    print("PASS: test_fm07_unused_imports")


def test_fm08_write_before_read_true_violation():
    detector = AIFailureModeDetector()
    bad_code = 'def process(data):\n    data = get_new_data()\n    return data'
    result = detector.detect(bad_code)
    fm08 = [v for v in result.violations if v.rule_id == "FM-08"]
    assert len(fm08) > 0, "FM-08 not detected for true overwrite"
    print("PASS: test_fm08_write_before_read_true_violation")


def test_fm08_transform_pattern_passes():
    """FM-08 should NOT flag `data = transform(data)` — this is valid Python."""
    detector = AIFailureModeDetector()
    good_code = 'def process(data):\n    data = transform(data)\n    return data'
    result = detector.detect(good_code)
    fm08 = [v for v in result.violations if v.rule_id == "FM-08"]
    assert len(fm08) == 0, f"FM-08 false positive on transform pattern: {fm08}"
    print("PASS: test_fm08_transform_pattern_passes")


def test_fm13_magic_numbers():
    detector = AIFailureModeDetector()
    bad_code = 'def calculate_fault_current(voltage):\n    return voltage / 0.457'
    result = detector.detect(bad_code)
    fm13 = [v for v in result.violations if v.rule_id == "FM-13"]
    assert len(fm13) > 0, "FM-13 not detected for magic number"
    print("PASS: test_fm13_magic_numbers")


def test_fm14_mock_assert():
    detector = AIFailureModeDetector()
    bad_code = 'mock_tool.assert_called_with("expected_arg")'
    result = detector.detect(bad_code)
    fm14 = [v for v in result.violations if v.rule_id == "FM-14"]
    assert len(fm14) > 0, f"FM-14 not detected for mock assert: {result.violations}"
    print("PASS: test_fm14_mock_assert")


def test_clean_code_passes_all():
    detector = AIFailureModeDetector()
    clean_code = '''
def calculate_power(voltage: float, current: float) -> float:
    if current == 0:
        raise ValueError("Current cannot be zero")
    return voltage * current
'''
    result = detector.detect(clean_code)
    must_fix = [v for v in result.violations if v.severity == GuardSeverity.MUST_FIX]
    assert len(must_fix) == 0, f"Clean code has MUST_FIX violations: {must_fix}"
    print("PASS: test_clean_code_passes_all")


# ============================================================================
# Test 3: Code Guard (23 rules + 14 AI failure modes)
# ============================================================================

def test_code_guard_long_function():
    guard = CodeGuard()
    lines = ["    x = 1"] * 55
    long_code = f'def very_long_function(data):\n{chr(10).join(lines)}\n    return x'
    result = guard.scan(long_code)
    cc01 = [v for v in result.violations if v.rule_id == "CC-01"]
    assert len(cc01) > 0, "CC-01 not detected for oversized function"
    print("PASS: test_code_guard_long_function")


def test_code_guard_too_many_params():
    guard = CodeGuard()
    bad_code = 'def process(a, b, c, d, e, f, g, h):\n    return a + b'
    result = guard.scan(bad_code)
    cc02 = [v for v in result.violations if v.rule_id == "CC-02"]
    assert len(cc02) > 0, "CC-02 not detected for too many parameters"
    print("PASS: test_code_guard_too_many_params")


def test_code_guard_high_complexity():
    guard = CodeGuard()
    complex_code = 'def f(x):\n' + '\n'.join(f'    if x > {i}: return {i}' for i in range(15))
    result = guard.scan(complex_code)
    cc17 = [v for v in result.violations if v.rule_id == "CC-17"]
    assert len(cc17) > 0, "CC-17 not detected for high complexity"
    print("PASS: test_code_guard_high_complexity")


# ============================================================================
# Test 4: Test Guard (9 + 3 rules)
# ============================================================================

def test_test_guard_mock_assert():
    guard = TestGuard()
    bad_test = 'def test_agent_calls_tool():\n    mock_tool.assert_called_with("expected")'
    result = guard.scan(bad_test)
    fm14 = [v for v in result.violations if v.rule_id == "FM-14"]
    assert len(fm14) > 0, f"FM-14 not detected by test guard: {result.violations}"
    print("PASS: test_test_guard_mock_assert")


def test_test_guard_poor_naming():
    guard = TestGuard()
    bad_test = 'def test_1():\n    assert True'
    result = guard.scan(bad_test)
    t05 = [v for v in result.violations if v.rule_id == "T-05"]
    assert len(t05) > 0, "T-05 not detected for numeric test name"
    print("PASS: test_test_guard_poor_naming")


def test_test_guard_llm_exact_assertion():
    guard = TestGuard()
    bad_test = 'def test_llm():\n    assert response == "Hello, how can I help you?"'
    result = guard.scan(bad_test)
    tl1 = [v for v in result.violations if v.rule_id == "T-L1"]
    assert len(tl1) > 0, "T-L1 not detected for exact string assertion on LLM output"
    print("PASS: test_test_guard_llm_exact_assertion")


# ============================================================================
# Test 5: Docs Guard (10 rules)
# ============================================================================

def test_docs_guard_unverifiable_claims():
    guard = DocsGuard()
    bad_docs = 'It is well-known that our engine is the fastest solution.\nEveryone knows that Newton-Raphson always converges.'
    result = guard.scan(bad_docs)
    d04 = [v for v in result.violations if v.rule_id == "D-04"]
    assert len(d04) > 0, "D-04 not detected for unverifiable claims"
    print("PASS: test_docs_guard_unverifiable_claims")


def test_docs_guard_filler():
    guard = DocsGuard()
    bad_docs = 'In this section, we will discuss the load flow analysis.\nIt is important to note that voltage matters.'
    result = guard.scan(bad_docs)
    d07 = [v for v in result.violations if v.rule_id == "D-07"]
    assert len(d07) > 0, "D-07 not detected for filler phrases"
    print("PASS: test_docs_guard_filler")


def test_docs_guard_vague_version():
    guard = DocsGuard()
    bad_docs = 'Install the latest version of numpy for best results.'
    result = guard.scan(bad_docs)
    d05 = [v for v in result.violations if v.rule_id == "D-05"]
    assert len(d05) > 0, "D-05 not detected for vague version"
    print("PASS: test_docs_guard_vague_version")


# ============================================================================
# Test 6: Engineering Code Integration Test
# ============================================================================

def test_etap_engineering_code_quality():
    """Test with real ETAP engineering code patterns."""
    guard = CodeGuard()
    eng_code = '''
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
    result = guard.scan(eng_code)
    must_fix = [v for v in result.violations if v.severity == GuardSeverity.MUST_FIX]
    assert len(must_fix) == 0, f"Engineering code has MUST_FIX: {[(v.rule_id, v.description) for v in must_fix]}"
    print("PASS: test_etap_engineering_code_quality")


def test_bad_engineering_code_detected():
    """Test that bad engineering code IS caught by the guards."""
    guard = CodeGuard()
    bad_eng_code = '''
import os
import re
import json
import xml.etree.ElementTree

def run_all_analyses(voltage, current, frequency, impedance, power, angle, temp, humidity, pressure, wind):
    try:
        result = voltage / current
    except:
        pass
    if result is None:
        result = {}
    return True
'''
    result = guard.scan(bad_eng_code)
    must_fix = [v for v in result.violations if v.severity == GuardSeverity.MUST_FIX]
    assert len(must_fix) > 0, f"Bad engineering code not caught: must_fix={len(must_fix)}"
    rule_ids = set(v.rule_id for v in must_fix)
    # Should detect: FM-01 (catch-all), FM-04 (hardcoded True), FM-07 (unused imports), FM-08 (overwrite)
    assert "FM-01" in rule_ids, f"FM-01 not in {rule_ids}"
    print(f"PASS: test_bad_engineering_code_detected (found: {rule_ids})")


# ============================================================================
# Test 7: CodeGuardAgent Integration
# ============================================================================

def test_code_guard_agent_initializes():
    from agents.code_guard_agent import CodeGuardAgent
    agent = CodeGuardAgent()
    assert agent.agent_name == "Code Guard Agent"
    assert agent.prompt_handle == "code_guard_agent"
    assert agent._code_guard is not None
    assert agent._test_guard is not None
    assert agent._docs_guard is not None
    assert agent._ai_detector is not None
    print("PASS: test_code_guard_agent_initializes")


# ============================================================================
# Test 8: Orchestrator Integration
# ============================================================================

def test_orchestrator_registers_guard_agent():
    from agents.orchestrator import ChiefEngineeringOrchestrator
    orch = ChiefEngineeringOrchestrator()
    assert 'code_guard' in orch.agents, "code_guard not registered in orchestrator"
    print("PASS: test_orchestrator_registers_guard_agent")


# ============================================================================
# Test 9: Guard API Endpoint Schema
# ============================================================================

def test_guard_review_request_model():
    """Validate the Pydantic model for guard review endpoint."""
    # This tests that the model can be instantiated
    try:
        from pydantic import BaseModel, Field
        from typing import Optional, Dict, Any

        class GuardReviewRequest(BaseModel):
            source: str = Field(..., description="Source code", min_length=1, max_length=500_000)
            guard_type: str = Field(default="all")
            language: str = Field(default="python")
            context: Optional[Dict[str, Any]] = Field(default=None)

        req = GuardReviewRequest(source="def hello(): pass")
        assert req.source == "def hello(): pass"
        assert req.guard_type == "all"
        print("PASS: test_guard_review_request_model")
    except ImportError:
        print("SKIP: test_guard_review_request_model (pydantic not available)")


# ============================================================================
# Test 10: Secure Executor Guard Integration
# ============================================================================

def test_secure_executor_guard_scan():
    """Test that the secure executor's guard scan logic works."""
    # Simulate what secure_executor does
    from guards.ai_failure_modes import AIFailureModeDetector, GuardSeverity

    # Code with catch-all — should be blocked
    bad_code = 'try:\n    x = compute()\nexcept:\n    pass'

    detector = AIFailureModeDetector()
    result = detector.detect(bad_code)

    must_fix = [v for v in result.violations if v.severity == GuardSeverity.MUST_FIX]
    assert len(must_fix) > 0, "Guard should detect MUST_FIX in bad code"

    # Clean code — should pass
    clean_code = 'def calc(v, i):\n    if i == 0:\n        raise ValueError("Zero")\n    return v / i'
    result2 = detector.detect(clean_code)
    must_fix2 = [v for v in result2.violations if v.severity == GuardSeverity.MUST_FIX]
    assert len(must_fix2) == 0, f"Clean code should pass guard: {must_fix2}"

    print("PASS: test_secure_executor_guard_scan")


# ============================================================================
# Test 11: Full Round-Trip — API Response Format
# ============================================================================

def test_guard_result_api_format():
    """Test that the full guard result serializes correctly for API responses."""
    guard = CodeGuard()
    code = '''
import os
def process(data):
    try:
        result = compute(data)
    except:
        pass
    return True
'''
    result = guard.scan(code)
    api_dict = result.to_dict()

    # Validate API response structure
    assert "guard_name" in api_dict
    assert "mode" in api_dict
    assert "passed" in api_dict
    assert "must_fix" in api_dict
    assert "should_fix" in api_dict
    assert "worth_noting" in api_dict
    assert "violations" in api_dict
    assert "metadata" in api_dict

    # Validate it's JSON-serializable
    json_str = json.dumps(api_dict)
    parsed = json.loads(json_str)
    assert parsed["guard_name"] == "code_guard"

    print("PASS: test_guard_result_api_format")


# ============================================================================
# Run All Tests
# ============================================================================

if __name__ == "__main__":
    tests = [
        test_severity_values,
        test_guard_result_passed,
        test_guard_result_failed,
        test_guard_result_should_fix_still_passes,
        test_to_dict_serialization,
        test_14_failure_modes_defined,
        test_fm01_catch_all_bare_except,
        test_fm01_broad_exception_swallowing,
        test_fm01_specific_exception_passes,
        test_fm04_hardcoded_success_return,
        test_fm04_derived_return_passes,
        test_fm07_unused_imports,
        test_fm08_write_before_read_true_violation,
        test_fm08_transform_pattern_passes,
        test_fm13_magic_numbers,
        test_fm14_mock_assert,
        test_clean_code_passes_all,
        test_code_guard_long_function,
        test_code_guard_too_many_params,
        test_code_guard_high_complexity,
        test_test_guard_mock_assert,
        test_test_guard_poor_naming,
        test_test_guard_llm_exact_assertion,
        test_docs_guard_unverifiable_claims,
        test_docs_guard_filler,
        test_docs_guard_vague_version,
        test_etap_engineering_code_quality,
        test_bad_engineering_code_detected,
        test_code_guard_agent_initializes,
        test_orchestrator_registers_guard_agent,
        test_guard_review_request_model,
        test_secure_executor_guard_scan,
        test_guard_result_api_format,
    ]

    passed = 0
    failed = 0
    errors = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append(f"{test.__name__}: {e}")
            print(f"FAIL: {test.__name__} — {e}")

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} PASSED, {failed} FAILED out of {len(tests)} tests")
    if errors:
        print("\nFAILED TESTS:")
        for err in errors:
            print(f"  - {err}")
    print(f"{'='*60}")

    if failed > 0:
        sys.exit(1)
