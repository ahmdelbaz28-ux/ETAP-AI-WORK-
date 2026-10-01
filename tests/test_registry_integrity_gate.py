"""
tests/test_registry_integrity_gate.py — M2.4 Registry Integrity Gate Tests.

Verifies that the check_registry_integrity.py guardian:
1. Passes (exit 0) for the clean repository state.
2. Fails (exit 1 / violations list) when a rogue study_type binding is planted.
3. Confirms STUDY_DISPATCH contains all StudyType enum values (strict mode).
"""

from __future__ import annotations

import importlib.util as _ilu
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Load the guardian script via path (scripts/ has no __init__.py)
_guard_path = REPO_ROOT / "scripts" / "check_registry_integrity.py"
_spec = _ilu.spec_from_file_location("check_registry_integrity", _guard_path)
_guard_module = _ilu.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_guard_module)  # type: ignore[union-attr]

_load_canonical_study_types = _guard_module._load_canonical_study_types
_scan_rogue_bindings = _guard_module._scan_rogue_bindings
run_registry_integrity_check = _guard_module.run_registry_integrity_check


# ---------------------------------------------------------------------------
# Fixture: plant a rogue binding in a temp file during the test
# ---------------------------------------------------------------------------

@pytest.fixture()
def rogue_py_file(tmp_path):
    """Write a Python file that references a non-existent study_type."""
    rogue = tmp_path / "rogue_agent.py"
    rogue.write_text(
        textwrap.dedent("""\
            # Simulated rogue binding — this study_type is NOT in the registry
            dispatch[\"totally_nonexistent_study\"] = \"SomeAgent\"
        """),
        encoding="utf-8",
    )
    return rogue


# ---------------------------------------------------------------------------
# 1. Clean repository scan returns no violations
# ---------------------------------------------------------------------------

def test_clean_repo_has_no_rogue_bindings():
    """Repository scan produces zero rogue binding violations in clean state."""
    canonical = _load_canonical_study_types()
    assert len(canonical) > 0, "Could not load canonical study types"
    violations = _scan_rogue_bindings(canonical)
    assert violations == [], (
        f"Expected zero violations in clean repo, got {len(violations)}:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


# ---------------------------------------------------------------------------
# 2. Rogue binding IS detected when planted
# ---------------------------------------------------------------------------

def test_rogue_binding_detected(rogue_py_file):
    """The guardian detects a planted rogue study_type binding using real scanner."""
    canonical = _load_canonical_study_types()

    # Invoke the real scanner with scan_dirs set to the directory containing rogue_py_file
    violations = _scan_rogue_bindings(canonical, scan_dirs=[rogue_py_file.parent])

    # Verify that the rogue study type was actively detected and flagged
    assert any("totally_nonexistent_study" in v for v in violations), (
        f"Expected real scanner to flag 'totally_nonexistent_study', got violations: {violations}"
    )


# ---------------------------------------------------------------------------
# 3. Strict mode: STUDY_DISPATCH must cover all StudyType enum values
# ---------------------------------------------------------------------------

def test_dispatch_covers_all_study_type_enum_values():
    """STUDY_DISPATCH keys must be a superset of StudyType enum values."""
    from agents.models import StudyType
    from engine.dispatch import STUDY_DISPATCH

    enum_values = {st.value for st in StudyType}
    dispatch_keys = set(STUDY_DISPATCH.keys())
    missing = enum_values - dispatch_keys
    assert not missing, (
        f"StudyType enum values not covered by STUDY_DISPATCH: {sorted(missing)}"
    )


# ---------------------------------------------------------------------------
# 4. Guardian function returns 0 in clean state
# ---------------------------------------------------------------------------

def test_run_registry_integrity_check_passes_on_clean_repo(capsys):
    """run_registry_integrity_check() returns 0 in the clean repo."""
    result = run_registry_integrity_check(strict=True)
    captured = capsys.readouterr()
    assert result == 0, (
        f"Expected exit 0, got {result}.\nstdout: {captured.out}\nstderr: {captured.err}"
    )
    assert "BLOCKED" not in captured.err, (
        f"Unexpected violations found:\n{captured.err}"
    )


# ---------------------------------------------------------------------------
# 5. All canonical study types are known (registry completeness sanity)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expected_type", [
    "load_flow", "short_circuit", "arc_flash", "protection_coordination",
    "harmonic_analysis", "optimal_power_flow", "motor_starting",
    "transient_stability", "cable_sizing", "earth_grid",
    "renewable_integration", "battery_storage", "scada", "digital_twin",
    "etap_expert", "etap_gui", "generative_design",
])
def test_canonical_study_types_present(expected_type):
    """Each expected canonical study type is present in STUDY_DISPATCH."""
    canonical = _load_canonical_study_types()
    assert expected_type in canonical, (
        f"'{expected_type}' is missing from canonical study type registry"
    )
