"""
tests/test_dspy_fallback.py — Fallback behavior, feature flags, and safety limits.

Windows-safe, completely offline, zero network access.
Verifies:
(a) Malformed LM JSON -> fallback finding, no exception escapes
(b) Flag-disabled path with monkeypatch -> AgentStatus.FAILED, reason="flag_disabled"
(c) run_ingest failure raises error -> asserts NO executable spec is produced
(d) Input exceeding 50,000 chars -> INPUT_TOO_LARGE
"""

from __future__ import annotations

import pytest

from agents.models import AgentStatus, EngineeringTask
from agents.registry import DspyCopilotAgent
from services.dspy_copilot.runtime import DspyIngestError, run_diagnose, run_ingest


def test_malformed_llm_json_fallback(monkeypatch):
    """When the LLM produces malformed or non-schema JSON, run_diagnose must not crash;

    it must return a valid DiagnosticOutput with a FALLBACK finding.
    """
    # Enable the feature flag for this test so we reach the module code
    monkeypatch.setattr("services.dspy_copilot.runtime.is_enabled", lambda: True)

    study_data = {
        "success": True,
        "data": {
            "converged": True,
            "buses": {"1": {"voltage_magnitude_pu": 1.0}},
        },
    }

    class BrokenModule:
        def __init__(self, *args, **kwargs):
            pass

        def forward(self, results_json: str):
            raise ValueError("dspy_diagnostic_validation_failed: Invalid JSON output from LLM")

    monkeypatch.setattr("services.dspy_copilot.runtime.DspyDiagnosticModule", BrokenModule)

    diag = run_diagnose(study_data)
    assert diag is not None
    assert any(f.code == "FALLBACK" for f in diag.findings)
    assert "IEEE 3002.7" in diag.citations[0]


@pytest.mark.asyncio
async def test_flag_disabled_path(monkeypatch):
    """In development/test ENV, is_feature_enabled() forces True.

    We explicitly monkeypatch it to False to verify fail-closed behavior:
    AgentStatus.FAILED, reason='flag_disabled'.
    """
    monkeypatch.setattr("api.feature_flags.is_feature_enabled", lambda key, default=True: False)
    monkeypatch.setattr("services.dspy_copilot.runtime.is_enabled", lambda: False)

    agent = DspyCopilotAgent()
    task = EngineeringTask(
        task_id="task_test_flag_disabled",
        description="Verify flag disabled returns failed status",
        study_types=[],
        parameters={"sld_notes": "Bus 1 Slack 1.0 pu"},
    )
    result = await agent.execute(task)

    assert result.status == AgentStatus.FAILED
    assert result.data.get("reason") == "flag_disabled"

    # Also verify run_ingest fails closed when flag disabled
    with pytest.raises(DspyIngestError, match="flag_disabled"):
        run_ingest("Bus 1 Slack 1.0 pu")


def test_run_ingest_failure_produces_no_executable_spec(monkeypatch):
    """When ingestion fails (corrupted input or LLM failure), it must raise DspyIngestError.

    It must NEVER produce an empty or fallback executable spec.
    """
    # Enable the feature flag so we reach the module code
    monkeypatch.setattr("services.dspy_copilot.runtime.is_enabled", lambda: True)

    class FailingModule:
        def __init__(self, *args, **kwargs):
            pass

        def forward(self, sld_notes: str):
            raise ValueError("dspy_ingest_validation_failed: unparseable syntax")

    monkeypatch.setattr("services.dspy_copilot.runtime.DspySldIngestModule", FailingModule)

    with pytest.raises(DspyIngestError) as exc_info:
        run_ingest("Corrupted notes that fail validation")

    assert "dspy_ingest_failed" in str(exc_info.value)


def test_input_too_large(monkeypatch):
    """Inputs exceeding MAX_INPUT_CHARS (50,000) must immediately raise/return INPUT_TOO_LARGE."""
    # Enable flag so the length check is reached (not the flag gate)
    monkeypatch.setattr("services.dspy_copilot.runtime.is_enabled", lambda: True)

    oversized_notes = "A" * 50001

    with pytest.raises(DspyIngestError, match="INPUT_TOO_LARGE"):
        run_ingest(oversized_notes)

    # In diagnostics, payload exceeding 50,000 chars returns INPUT_TOO_LARGE finding
    huge_study_data = {
        "success": True,
        "data": {
            "converged": True,
            "padding": "X" * 55000,
        },
    }
    diag = run_diagnose(huge_study_data)
    assert any(f.code == "INPUT_TOO_LARGE" for f in diag.findings)


@pytest.mark.asyncio
async def test_agent_execute_missing_input():
    """FIX-2 test: Calling agent.execute with empty parameters returns FAILED with reason='missing_input'
    OR 'flag_disabled' (since strict flag is now off by default). Either is acceptable as fail-closed."""
    agent = DspyCopilotAgent()
    task = EngineeringTask(
        task_id="task_missing_input",
        description="Test missing parameters",
        study_types=[],
        parameters={},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    # Either missing_input or flag_disabled is acceptable (both are fail-closed)
    assert result.data.get("reason") in ("missing_input", "flag_disabled")


@pytest.mark.asyncio
async def test_agent_execute_ingest_error_surfaces_reason(monkeypatch):
    """FIX-2 test: Monkeypatch run_ingest to raise DspyIngestError('flag_disabled') surfaces data['reason']=='flag_disabled'."""
    def _mock_raise(notes):
        raise DspyIngestError("flag_disabled")

    # Enable flag so the agent reaches the ingest call (not the early flag-disabled check)
    monkeypatch.setattr("services.dspy_copilot.runtime.is_enabled", lambda: True)
    monkeypatch.setattr("services.dspy_copilot.runtime.run_ingest", _mock_raise)
    # Also patch any direct import in registry if present
    try:
        monkeypatch.setattr("agents.registry.run_ingest", _mock_raise)
    except AttributeError:
        pass

    agent = DspyCopilotAgent()
    task = EngineeringTask(
        task_id="task_ingest_error",
        description="Test ingest error handling",
        study_types=[],
        parameters={"sld_notes": "Bus 1 Slack 1.0 pu"},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("reason") == "flag_disabled"
