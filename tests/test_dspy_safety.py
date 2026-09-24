"""
tests/test_dspy_safety.py — Architectural integrity, solver isolation, and import safety.

Windows-safe, completely offline, zero network access.
Verifies:
1. No physics solver or Ybus code exists inside services/dspy_copilot
2. Importing services.dspy_copilot.runtime does NOT import load_flow.load_flow
3. When dspy is not installed, importing succeeds and execution fails closed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_forbidden_physics_tokens():
    """Verify that services/dspy_copilot contains ZERO solver/physics implementations."""
    forbidden = ("LoadFlowSolver", "Ybus", "Newton")
    copilot_dir = Path("services/dspy_copilot")
    assert copilot_dir.exists(), "services/dspy_copilot must exist"

    hits = [
        (p.name, token)
        for p in copilot_dir.rglob("*.py")
        for token in forbidden
        if token in p.read_text(encoding="utf-8")
    ]
    assert hits == [], f"Forbidden physics/solver tokens found in copilot code: {hits}"


def test_import_runtime_does_not_pull_load_flow_solver():
    """Importing services.dspy_copilot.runtime must never eagerly import load_flow.load_flow."""
    # Evict modules if present
    for mod in list(sys.modules.keys()):
        if mod.startswith("load_flow") or mod.startswith("services.dspy_copilot"):
            sys.modules.pop(mod, None)

    import services.dspy_copilot.runtime  # noqa: F401

    assert "load_flow.load_flow" not in sys.modules, (
        "Eagerly imported load_flow.load_flow when loading copilot runtime!"
    )


def test_dspy_not_installed_scenario(monkeypatch):
    """When dspy is not installed, importing copilot modules succeeds,

    and calling run_ingest fails closed with a clean error.
    """
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "dspy" or name.startswith("dspy."):
            raise ImportError(f"No module named '{name}' (simulated missing dependency)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    # Calling run_ingest without dspy installed must raise DspyIngestError (fail-closed)
    from services.dspy_copilot.runtime import DspyIngestError, run_ingest

    with pytest.raises(DspyIngestError, match="dspy"):
        run_ingest("Bus 1 Slack 1.0 pu")
