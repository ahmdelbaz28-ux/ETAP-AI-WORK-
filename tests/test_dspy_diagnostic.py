"""
tests/test_dspy_diagnostic.py — Tests for DSPy Diagnostic Copilot and deterministic guards.

Windows-safe, completely offline, zero network access.
Verifies V-BAND and OVERLOAD detection, Q-LIMIT suppression when system_spec=None,
mocked LLM enhancement, and guards winning over LLM omissions.
"""

from __future__ import annotations

import json

import pytest

from core_model.specs import BusSpec, LineSpec, StudyResult, SystemSpec
from services.dspy_copilot.metrics import check_physics_guards
from services.dspy_copilot.modules import DspyDiagnosticModule
from services.dspy_copilot.runtime import run_diagnose
from services.dspy_copilot.schemas import DiagnosticFinding, DiagnosticOutput


def test_check_physics_guards_vband_and_overload():
    """Verify check_physics_guards detects V-BAND and OVERLOAD, and avoids fabricating Q-LIMIT."""
    study_data = {
        "success": True,
        "data": {
            "converged": True,
            "buses": {
                "1": {"voltage_magnitude_pu": 1.0, "voltage_angle_deg": 0.0},
                "2": {"voltage_magnitude_pu": 0.92, "voltage_angle_deg": -3.1},
            },
            "lines": [
                {"line_id": 1, "loading_pct": 112.0},
            ],
        },
    }

    # When system_spec is None, Q-LIMIT must NOT be fabricated
    findings = check_physics_guards(system_spec=None, study_data=study_data)
    codes = {f.code for f in findings}

    assert "V-BAND" in codes
    assert "OVERLOAD" in codes
    assert "Q-LIMIT" not in codes
    assert "DIVERGED" not in codes

    # Check finding details
    v_finding = next(f for f in findings if f.code == "V-BAND")
    assert v_finding.severity == "violation"
    assert v_finding.bus_id == 2
    assert "ANSI C84.1" in (v_finding.standard_ref or "")


def test_check_physics_guards_diverged():
    """Verify solver divergence is flagged as a violation."""
    study_data = {
        "success": False,
        "data": {
            "converged": False,
            "buses": {},
        },
    }
    findings = check_physics_guards(system_spec=None, study_data=study_data)
    assert any(f.code == "DIVERGED" and f.severity == "violation" for f in findings)


def test_guards_win_over_mocked_llm_that_drops_violation(monkeypatch):
    """Guards must win: if a mocked LLM emits a report that omitted V-BAND or OVERLOAD,

    run_diagnose must preserve all deterministic guard findings.
    """
    study_data = {
        "success": True,
        "data": {
            "converged": True,
            "buses": {
                "2": {"voltage_magnitude_pu": 0.92},
            },
            "lines": [
                {"line_id": 1, "loading_pct": 112.0},
            ],
        },
    }

    # Mock DspyDiagnosticModule forward to return report with NO violations (trying to drop them)
    class MockDiagnosticModule:
        def __init__(self, *args, **kwargs):
            pass

        def forward(self, results_json: str) -> DiagnosticOutput:
            return DiagnosticOutput(
                summary="AI claims everything is perfectly balanced and normal without issues.",
                findings=[
                    DiagnosticFinding(
                        severity="info",
                        code="AI_NOTE",
                        message="Routine check completed",
                        bus_id=None,
                        standard_ref=None,
                    )
                ],
                recommendations=["No physical action needed."],
                citations=["IEEE 3002.7"],
            )

    monkeypatch.setattr(
        "services.dspy_copilot.runtime.DspyDiagnosticModule",
        MockDiagnosticModule,
    )

    out = run_diagnose(study_data=study_data, system_spec=None)
    codes = {f.code for f in out.findings}

    # Guards MUST have won and added the missing V-BAND and OVERLOAD
    assert "V-BAND" in codes
    assert "OVERLOAD" in codes
    assert "AI_NOTE" in codes
    assert "IEEE 3002.7" in out.citations


def test_guards_win_over_colliding_llm_softer_severity(monkeypatch):
    """FIX-1 regression test: If LLM emits a colliding code (e.g. V-BAND) with softer severity ('info'),

    the deterministic guard finding (severity='violation') MUST win and the LLM finding MUST be discarded.
    """
    study_data = {
        "success": True,
        "data": {
            "converged": True,
            "buses": {
                "2": {"voltage_magnitude_pu": 0.92},
            },
        },
    }

    class CollidingDiagnosticModule:
        def __init__(self, *args, **kwargs):
            pass

        def forward(self, results_json: str) -> DiagnosticOutput:
            return DiagnosticOutput(
                summary="AI downplays voltage band violation to info.",
                findings=[
                    DiagnosticFinding(
                        severity="info",
                        code="V-BAND",
                        message="AI claims bus voltage is just fine and informational",
                        bus_id=2,
                        standard_ref="AI-Custom",
                    )
                ],
                recommendations=[],
                citations=[],
            )

    monkeypatch.setattr(
        "services.dspy_copilot.runtime.DspyDiagnosticModule",
        CollidingDiagnosticModule,
    )

    out = run_diagnose(study_data=study_data, system_spec=None)
    vband_findings = [f for f in out.findings if f.code == "V-BAND"]

    assert len(vband_findings) == 1
    assert vband_findings[0].severity == "violation"
    assert vband_findings[0].severity != "info"


def test_check_physics_guards_overload_traceability():
    """FIX-6 test: OVERLOAD findings populate bus_id from from_bus_id or to_bus_id."""
    study_data = {
        "success": True,
        "data": {
            "converged": True,
            "lines": [
                {"line_id": 10, "loading_pct": 125.0, "from_bus_id": 5, "to_bus_id": 6},
            ],
        },
    }
    findings = check_physics_guards(system_spec=None, study_data=study_data)
    overloads = [f for f in findings if f.code == "OVERLOAD"]
    assert len(overloads) == 1
    assert overloads[0].bus_id == 5

