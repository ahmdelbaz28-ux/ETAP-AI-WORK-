"""
tests/test_dspy_baseline_gate.py — Verification of DSPy fail-by-default behavior contract.

Windows-safe, completely offline, zero network access.
Verifies the gate criteria for P0:
(a) Strict feature flag 'dspy_copilot' is False by default across all environments.
(b) run_ingest raises DspyIngestError("flag_disabled") when flag is inactive (services/dspy_copilot/runtime.py:131-133).
(c) run_diagnose returns DiagnosticOutput with code="FLAG_DISABLED" when flag is inactive (services/dspy_copilot/runtime.py:202-214).
"""

from __future__ import annotations

import pytest

from api.feature_flags import is_strict_feature_enabled


def _load_runtime_module():
    """Load runtime module from merged codebase.

    If the runtime is not merged into the active tree, skip execution
    per docs/ai-integration/dspy-archive-decision.md.
    """
    try:
        from services.dspy_copilot.runtime import DspyIngestError, run_diagnose, run_ingest
        return run_ingest, run_diagnose, DspyIngestError
    except Exception:
        pytest.skip("dspy runtime not merged yet — see docs/ai-integration/dspy-archive-decision.md")


def test_dspy_flag_disabled_by_default():
    """Witness: Strict feature flag 'dspy_copilot' must be disabled by default."""
    enabled = is_strict_feature_enabled("dspy_copilot", default=False)
    assert enabled is False, "Feature flag 'dspy_copilot' must be False by default"


def test_run_ingest_fails_closed_when_flag_disabled():
    """Witness: services/dspy_copilot/runtime.py:131-133

    When flag is disabled, run_ingest must raise DspyIngestError('flag_disabled').
    Never produces an executable spec or silent fallback.
    """
    run_ingest, _, DspyIngestError = _load_runtime_module()

    with pytest.raises(DspyIngestError, match="flag_disabled"):
        run_ingest("Bus 1 Slack 1.0 pu")


def test_run_diagnose_degrades_gracefully_when_flag_disabled():
    """Witness: services/dspy_copilot/runtime.py:202-214

    When flag is disabled, run_diagnose must return DiagnosticOutput with code='FLAG_DISABLED'.
    """
    _, run_diagnose, _ = _load_runtime_module()

    diag = run_diagnose({"data": {"converged": True}})
    assert diag is not None
    assert any(finding.code == "FLAG_DISABLED" for finding in diag.findings)
    assert "Feature flag 'dspy_copilot' is inactive" in [f.message for f in diag.findings]
