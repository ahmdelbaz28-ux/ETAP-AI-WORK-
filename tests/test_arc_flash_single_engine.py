"""
Regression tests for single-engine architecture (arc flash)
==========================================================

Verifies the architectural promise documented in
``docs/SINGLE_ENGINE_ARCHITECTURE_ENFORCEMENT_REPORT.md``:

    Running an arc flash study via the ``arcFlashAgent`` ``run_python`` tool
    path must produce results numerically identical to running the same study
    via a direct call to ``PowerSystemEngine.run_study('arc_flash', ...)``.

Both paths must funnel through ``PowerSystemEngine`` — no parallel
computation, no inline IEEE 1584-2018 code, no shortcuts.

The "run_python path" is exercised by spawning the same Python process the
Mastra ``python-tool.ts`` spawns (``security/secure_executor.py``) and
piping representative code through stdin. This is an integration test that
exercises:

  1. The agent-facing tool surface (subprocess + stdin)
  2. The secure executor's AST-based import validation
  3. The ``PowerSystemEngine`` dispatcher's ``'arc_flash'`` branch
  4. The IEEE 1584-2018 implementation in ``fault_analysis.ArcFlashEngine``
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Add project root to sys.path so the `engine` and `security` packages
# resolve identically whether the test is run from `tests/` or the root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.engine import PowerSystemEngine  # noqa: E402

SECURE_EXECUTOR = PROJECT_ROOT / "security" / "secure_executor.py"

# ---------------------------------------------------------------------------
# Reference study parameters
# ---------------------------------------------------------------------------
# 4.16 kV switchgear, 20 kA bolted fault, 0.183 s arcing time, 610 mm (24 in)
# working distance, VCB electrode, typical box enclosure. These are the
# defaults used elsewhere in the test suite and the agent prompt examples.
STUDY_PARAMS: dict = {
    "voltage_kv": 4.16,
    "bolted_fault_current_ka": 20.0,
    "arc_duration_sec": 0.183,
    "working_distance_mm": 610.0,
    "electrode_config": "VCB",
    "enclosure_type": "box",
}

# Fields compared between the two paths. String fields must match exactly
# (e.g. method label, PPE category, electrode configuration). Numeric
# fields are compared against the per-field tolerances below.
COMPARED_FIELDS = (
    "incident_energy_cal_per_cm2",
    "incident_energy_at_full_arc_current",
    "incident_energy_at_reduced_arc_current",
    "arc_flash_boundary_mm",
    "arc_flash_boundary_in",
    "arc_current_ka",
    "reduced_arc_current_ka",
    "ppe_level",
    "method",
    "electrode_configuration",
    "enclosure_type",
    "voltage_kv",
    "bolted_fault_current_ka",
    "arc_duration_sec",
    "working_distance_mm",
)

# Per-field absolute tolerances. Tight enough to catch genuine divergence
# between paths; loose enough to absorb IEEE 1584-2018 rounding (the
# reference results are rounded to 4 decimal places / 1 decimal mm).
TOLERANCES: dict = {
    "incident_energy_cal_per_cm2": 1e-4,
    "incident_energy_at_full_arc_current": 1e-4,
    "incident_energy_at_reduced_arc_current": 1e-4,
    "arc_flash_boundary_mm": 1e-1,
    "arc_flash_boundary_in": 1e-2,
    "arc_current_ka": 1e-4,
    "reduced_arc_current_ka": 1e-4,
    "voltage_kv": 1e-9,
    "bolted_fault_current_ka": 1e-9,
    "arc_duration_sec": 1e-9,
    "working_distance_mm": 1e-9,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _run_direct_engine(params: dict) -> dict:
    """Path 1 — direct in-process call to PowerSystemEngine.run_study()."""
    engine = PowerSystemEngine()  # arc flash does not need a network model
    return engine.run_study(study_type="arc_flash", **params)


def _build_agent_code(params: dict) -> str:
    """Python code that the agent's LLM would produce — identical to the
    pattern ``loadFlowAgent`` / ``shortCircuitAgent`` / etc. follow.

    The code imports ``engine``, instantiates the engine, calls
    ``run_study('arc_flash', ...)``, and prints the result as JSON to stdout
    for the secure executor to capture.
    """
    # json.dumps gives us a safe, well-formed kwargs literal.
    params_literal = json.dumps(params)
    return (
        "import json\n"
        "from engine.engine import PowerSystemEngine\n"
        "engine = PowerSystemEngine()\n"
        f"result = engine.run_study(study_type='arc_flash', **{params_literal})\n"
        "print(json.dumps(result))\n"
    )


def _run_via_run_python(params: dict, *, timeout: int = 30) -> dict:
    """Path 2 — exercise the run_python tool end-to-end.

    Spawns ``security/secure_executor.py`` (the exact binary the TypeScript
    ``python-tool.ts`` spawns) with the agent's Python code piped through
    stdin, and parses the JSON wrapper it returns. The inner ``print(json.dumps(...))``
    becomes the ``output`` field of the executor's response; we parse that
    a second time to recover the dict.
    """
    if not SECURE_EXECUTOR.exists():
        pytest.skip(f"secure_executor.py not found at {SECURE_EXECUTOR}")

    code = _build_agent_code(params)

    proc = subprocess.run(
        [sys.executable, str(SECURE_EXECUTOR)],
        input=code,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )

    if proc.returncode != 0:
        pytest.fail(
            "secure_executor.py exited with code "
            f"{proc.returncode}.\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )

    try:
        wrapper = json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        pytest.fail(
            "secure_executor.py returned non-JSON wrapper.\n"
            f"STDOUT: {proc.stdout!r}\nSTDERR: {proc.stderr!r}\nError: {exc}"
        )

    if not wrapper.get("success"):
        pytest.fail(
            f"secure_executor.py reported failure: {wrapper.get('error')!r}\nSTDERR:\n{proc.stderr}"
        )

    # The inner print(json.dumps(result)) lives in the 'output' field as a
    # JSON-encoded string. Parse it back into a dict.
    try:
        return json.loads(wrapper["output"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        pytest.fail(f"Could not parse agent-path output as JSON: {exc}\nwrapper: {wrapper!r}")


def _assert_results_agree(direct: dict, agent: dict) -> None:
    """Assert every compared field matches within tolerance."""
    mismatches: list[str] = []
    for field in COMPARED_FIELDS:
        assert field in direct, f"Direct result missing field {field!r}"
        assert field in agent, f"Agent-path result missing field {field!r}"

        d_val = direct[field]
        a_val = agent[field]

        if isinstance(d_val, str):
            if d_val != a_val:
                mismatches.append(f"  - {field!r}: direct={d_val!r}, agent={a_val!r}")
            continue

        if isinstance(d_val, bool) or isinstance(a_val, bool):
            if d_val != a_val:
                mismatches.append(f"  - {field!r}: direct={d_val!r}, agent={a_val!r}")
            continue

        tol = TOLERANCES.get(field, 1e-6)
        if abs(float(d_val) - float(a_val)) > tol:
            mismatches.append(
                f"  - {field!r}: direct={d_val}, agent={a_val}, "
                f"diff={abs(float(d_val) - float(a_val)):.3e} > tol={tol}"
            )

    if mismatches:
        raise AssertionError(
            "Direct and run_python paths disagree on arc flash result:\n" + "\n".join(mismatches)
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestArcFlashSingleEngine:
    """Regression tests for the arc-flash single-engine architecture."""

    def test_direct_engine_path_returns_ieee_1584_result(self) -> None:
        """PowerSystemEngine.run_study('arc_flash', ...) returns a well-formed
        IEEE 1584-2018 result for the canonical 4.16 kV reference case."""
        result = _run_direct_engine(STUDY_PARAMS)

        # Result is a dict with all the IEEE 1584-2018 keys.
        assert isinstance(result, dict)
        assert result["method"] == "IEEE 1584-2018"
        assert result["electrode_configuration"] == "VCB"
        assert result["enclosure_type"] == "box"
        assert result["voltage_kv"] == pytest.approx(STUDY_PARAMS["voltage_kv"])
        assert result["bolted_fault_current_ka"] == pytest.approx(
            STUDY_PARAMS["bolted_fault_current_ka"]
        )
        # Engineering invariants.
        assert result["arc_current_ka"] > 0
        # The engine rounds both values to 4 dp, so we compare the
        # round-of-product against the round-of-factor-times-round:
        # both should match to 4 dp (IEEE 1584-2018 working precision).
        assert result["reduced_arc_current_ka"] == pytest.approx(
            0.85 * result["arc_current_ka"], rel=1e-3
        )
        assert result["incident_energy_cal_per_cm2"] >= 0
        assert result["arc_flash_boundary_mm"] >= 0
        # PPE level is one of the documented categories.
        assert result["ppe_level"] in {"0", "1", "2", "3", "4", "DANGER"}

    def test_run_python_path_returns_same_shape(self) -> None:
        """The run_python tool path (via secure_executor.py) returns the
        same dict shape as the direct path."""
        result = _run_via_run_python(STUDY_PARAMS)

        assert isinstance(result, dict)
        for field in COMPARED_FIELDS:
            assert field in result, f"Agent-path result missing field {field!r}"

    def test_run_python_path_reaches_engine(self) -> None:
        """Sanity: the agent-path result has engine-specific markers that
        confirm the code reached PowerSystemEngine (not a self-contained
        fallback). If this fails, the agent's run_python is silently
        bypassed and the single-engine contract is broken."""
        result = _run_via_run_python(STUDY_PARAMS)
        # The engine dispatcher stamps 'method' with the IEEE 1584-2018
        # label. A self-contained fallback would use 'Ralph Lee'.
        assert result["method"] == "IEEE 1584-2018"
        # The engine round-trips the electrode config string back exactly.
        assert result["electrode_configuration"] == STUDY_PARAMS["electrode_config"]
        assert result["enclosure_type"] == STUDY_PARAMS["enclosure_type"]

    def test_both_paths_produce_identical_results(self) -> None:
        """Core regression test.

        Run the same arc flash study via the two paths and assert every
        compared field matches within numerical tolerance. This is the
        single-engine invariant: both paths must funnel through
        PowerSystemEngine and therefore produce numerically identical
        results.
        """
        direct = _run_direct_engine(STUDY_PARAMS)
        agent = _run_via_run_python(STUDY_PARAMS)
        _assert_results_agree(direct, agent)


class TestArcFlashSingleEngineScenarios:
    """Parametrised regression across diverse arc flash scenarios.

    Exercises the parametric envelope (low/mid/high energy, different
    electrode configurations, different enclosure types) to make sure the
    single-engine invariant holds for the full operating range, not just
    the canonical 4.16 kV reference case.
    """

    @pytest.mark.parametrize(
        "scenario",
        [
            pytest.param(
                {
                    "label": "low_voltage_480V_VCB",
                    "params": {
                        "voltage_kv": 0.48,
                        "bolted_fault_current_ka": 5.0,
                        "arc_duration_sec": 0.05,
                        "working_distance_mm": 610.0,
                        "electrode_config": "VCB",
                        "enclosure_type": "box",
                    },
                },
                id="low_voltage_480V_VCB",
            ),
            pytest.param(
                {
                    "label": "mid_voltage_4kV_VCBB",
                    "params": {
                        "voltage_kv": 4.16,
                        "bolted_fault_current_ka": 20.0,
                        "arc_duration_sec": 0.183,
                        "working_distance_mm": 610.0,
                        "electrode_config": "VCBB",
                        "enclosure_type": "box",
                    },
                },
                id="mid_voltage_4kV_VCBB",
            ),
            pytest.param(
                {
                    "label": "high_energy_13kV_VOA_open",
                    "params": {
                        "voltage_kv": 13.8,
                        "bolted_fault_current_ka": 40.0,
                        "arc_duration_sec": 0.5,
                        "working_distance_mm": 910.0,
                        "electrode_config": "VOA",
                        "enclosure_type": "open",
                    },
                },
                id="high_energy_13kV_VOA_open",
            ),
        ],
    )
    def test_paths_agree_across_scenarios(self, scenario: dict) -> None:
        direct = _run_direct_engine(scenario["params"])
        agent = _run_via_run_python(scenario["params"])
        _assert_results_agree(direct, agent)


class TestArcFlashRunPythonSecurityBoundary:
    """Verify the run_python path is still gated by the security framework.

    These tests make sure adding the single-engine integration has not
    weakened the import allow-list enforced by the secure executor.
    """

    def test_disallowed_import_is_rejected(self) -> None:
        """Code that imports a module outside the allow-list must be rejected
        by the validator, even when it ultimately tries to call the engine."""
        if not SECURE_EXECUTOR.exists():
            pytest.skip(f"secure_executor.py not found at {SECURE_EXECUTOR}")

        # `socket` is NOT in the validator's allow-list.
        bad_code = (
            "import socket\n"  # disallowed import
            "import json\n"
            "from engine.engine import PowerSystemEngine\n"
            "print(json.dumps({'sneaky': True}))\n"
        )
        proc = subprocess.run(
            [sys.executable, str(SECURE_EXECUTOR)],
            input=bad_code,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        # The validator rejects the code BEFORE execution, so the executor
        # exits with success=False and a security-violation message. The
        # process exit code is 1 in that case.
        assert proc.returncode != 0, "secure_executor should reject code with disallowed imports"
        # And the wrapper should report the violation clearly.
        wrapper = json.loads(proc.stdout.strip())
        assert wrapper.get("success") is False
        assert "Forbidden" in wrapper.get("error", "") or "Unauthorized" in wrapper.get("error", "")

    def test_whitelisted_engine_imports_pass_validation(self) -> None:
        """All whitelisted engine imports must pass AST-level validation —
        confirming the __import__ fix in secure_executor.py enables the
        allow-list to work end-to-end.

        Without __import__ in safe_globals, importing 'engine' or
        'fault_analysis' at exec() time would fail even though the AST
        validator approved them. This test is the positive canary.
        """
        from security.security_framework import InputValidator

        # validate_python_code is a static method on InputValidator.
        # Passing allowed_imports=None uses the method's internal default set.
        # These are the modules that the validator approves at AST-parse time;
        # secure_executor.py adds __import__ to safe_globals so they also work
        # at exec() time (where Python would otherwise refuse them).
        for module in (
            "engine",
            "fault_analysis",
            "relays",
            "coordination",
            "load_flow",
        ):
            code = f"import {module}"
            result = InputValidator.validate_python_code(code, None)  # NOSONAR — S5655: intentional wrong-type arg to verify validation rejects it
            assert result is True, f"Validator should allow '{module}' (whitelisted)"

    def test_forbidden_builtin_call_is_rejected(self) -> None:
        """Direct calls to ``__import__`` (or eval/exec) must be rejected."""
        if not SECURE_EXECUTOR.exists():
            pytest.skip(f"secure_executor.py not found at {SECURE_EXECUTOR}")

        bad_code = "result = __import__('os').system('echo PWNED')\n"
        proc = subprocess.run(
            [sys.executable, str(SECURE_EXECUTOR)],
            input=bad_code,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
            env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
        )
        assert proc.returncode != 0, "secure_executor should reject direct __import__ calls"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
