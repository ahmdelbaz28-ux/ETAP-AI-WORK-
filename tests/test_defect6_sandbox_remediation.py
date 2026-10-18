"""
Regression tests for Defect 6:
- Python sandbox forbids direct import/execution of canonical engineering calculation engines.
- Safe advisory calculations (math, unit conversions, scientific arrays) are preserved.
- Direct canonical gateway request_canonical_execution is accepted and enforced.
- Tool discipline enforcement validates computational tool usage across aliases.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from api.agent_executor import _run_python_executor
from guards.prompt_rule_enforcement import (
    GuardSeverity,
    enforce_at_api_boundary,
    validate_agent_response,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SECURE_EXECUTOR = PROJECT_ROOT / "security" / "secure_executor.py"
ENV = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT)}


def test_safe_advisory_math_and_scientific_calculations_work():
    """1. Safe auxiliary computations (numpy, scipy, math, json) in secure_executor work."""
    code = (
        "import math\n"
        "import numpy as np\n"
        "import json\n"
        "val = math.sqrt(144) * float(np.sum([1, 2, 3]))\n"
        "print(json.dumps({'result': val}))\n"
    )
    proc = subprocess.run(
        [sys.executable, str(SECURE_EXECUTOR)],
        input=code,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(PROJECT_ROOT),
        env=ENV,
    )
    assert proc.returncode == 0
    wrapper = json.loads(proc.stdout.strip())
    assert wrapper.get("success") is True
    data = json.loads(wrapper["output"])
    assert data["result"] == 72.0


def test_importing_canonical_calculation_engines_in_sandbox_is_rejected():
    """2. Direct import of canonical calculation engines (engine, load_flow, fault_analysis) is REJECTED."""
    bad_code = (
        "import engine\n"
        "print('SHOULD NOT REACH HERE')\n"
    )
    proc = subprocess.run(
        [sys.executable, str(SECURE_EXECUTOR)],
        input=bad_code,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(PROJECT_ROOT),
        env=ENV,
    )
    assert proc.returncode != 0
    wrapper = json.loads(proc.stdout.strip())
    assert wrapper.get("success") is False
    assert (
        "Unauthorized" in wrapper.get("error", "")
        or "Forbidden" in wrapper.get("error", "")
        or "Sandbox escape" in wrapper.get("error", "")
    )


@pytest.mark.asyncio
async def test_attempting_canonical_study_via_run_python_executor_is_rejected():
    """3. Passing a reference study or code importing engines to _run_python_executor is REJECTED even without keywords in goal."""
    # A. Direct capability_id/study_type bypass attempt
    with pytest.raises(ValueError, match="cannot be executed via advisory run_python"):
        await _run_python_executor(
            args={
                "system": {"buses": [{"bus_id": "B1"}], "lines": []},
                "capability_id": "load_flow",
                "goal": "advisory scratch calculation",  # innocent-looking goal
            },
            ctx={"tenant_id": "test_tenant", "execution_id": "exec_1"},
        )

    # B. Code calling PowerSystemEngine directly with innocuous goal
    with pytest.raises(ValueError, match="Canonical calculation engine"):
        await _run_python_executor(
            args={
                "system": {"buses": [{"bus_id": "B1"}], "lines": []},
                "code": "from engine.engine import PowerSystemEngine\neng = PowerSystemEngine()",
                "goal": "helper calculation",
            },
            ctx={"tenant_id": "test_tenant", "execution_id": "exec_2"},
        )


def test_prompt_rule_enforcement_accepts_canonical_execution_or_run_python():
    """4 & 5. Tool rules accept canonical execution tools or run_python, and enforce at API boundary."""
    valid_text = (
        "Standard: IEEE 1584-2018. Assumptions: typical box enclosure. "
        "Incident energy: 4.2 cal/cm², PPE Category 2, Arc flash boundary: 1200 mm"
    )

    # A. Agent called request_canonical_execution -> MUST PASS tool discipline
    res_canonical = validate_agent_response(
        agent_id="arcflash-agent",
        response_text=valid_text,
        tool_calls_made=["request_canonical_execution"],
    )
    assert res_canonical.passed is True
    assert not any(v.rule_id == "F03-TOOL-computational-tool" for v in res_canonical.violations)

    # B. Agent called hyphenated alias request-canonical-execution -> MUST PASS
    res_alias = validate_agent_response(
        agent_id="arcflash-agent",
        response_text=valid_text,
        tool_calls_made=["request-canonical-execution"],
    )
    assert res_alias.passed is True

    # C. Agent called run_python for advisory calculation with explicit is_advisory=True -> MUST PASS
    res_advisory = validate_agent_response(
        agent_id="load-flow-agent",
        response_text="Standard: IEEE 3002.7. Voltage drop calculation: 2.1 %",
        tool_calls_made=["run_python"],
        is_advisory=True,
    )
    assert res_advisory.passed is True

    # C2. Authoritative agent calling run_python WITHOUT explicit is_advisory=True -> MUST FAIL
    res_unauthorized_advisory = validate_agent_response(
        agent_id="load-flow-agent",
        response_text="Standard: IEEE 3002.7. Voltage drop calculation: 2.1 %",
        tool_calls_made=["run_python"],
        is_advisory=False,
    )
    assert res_unauthorized_advisory.passed is False
    assert any(v.rule_id == "F03-TOOL-canonical-execution" for v in res_unauthorized_advisory.violations)

    # D. Agent made NO tool call -> MUST FAIL MUST_FIX for life-safety agent
    res_no_tool = validate_agent_response(
        agent_id="arcflash-agent",
        response_text=valid_text,
        tool_calls_made=[],
    )
    assert res_no_tool.passed is False
    assert any(v.severity == GuardSeverity.MUST_FIX for v in res_no_tool.violations)

    # E. Verify enforce_at_api_boundary blocks MUST_FIX response
    blocked_response = enforce_at_api_boundary(
        agent_id="arcflash-agent",
        response={"content": valid_text, "tool_calls": []},
    )
    assert blocked_response["success"] is False
    assert "Response blocked by prompt rule enforcement" in blocked_response["error"]


def test_legacy_sandbox_switch_cannot_bypass_in_production():
    """Setting ETAP_ALLOW_SANDBOX_CANONICAL_ENGINES=1 cannot activate bypass in production environment."""
    prod_env = {
        **ENV,
        "ENVIRONMENT": "production",
        "ETAP_ALLOW_SANDBOX_CANONICAL_ENGINES": "1",
    }
    # Remove PYTEST_CURRENT_TEST to simulate non-test production environment
    prod_env.pop("PYTEST_CURRENT_TEST", None)

    code = "import engine\nprint('SECURITY_VIOLATION')"
    proc = subprocess.run(
        [sys.executable, str(SECURE_EXECUTOR)],
        input=code,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(PROJECT_ROOT),
        env=prod_env,
    )
    assert proc.returncode != 0
    wrapper = json.loads(proc.stdout.strip())
    assert wrapper.get("success") is False
    assert "Unauthorized" in wrapper.get("error", "") or "Forbidden" in wrapper.get("error", "")
