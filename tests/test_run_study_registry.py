"""
Unit tests for the PowerSystemEngine.run_study registry.

These tests document the registry structure that the refactored
``run_study`` must use, and the validation semantics it must preserve.

The registry is an internal implementation detail of ``engine/engine.py``.
It is NOT exported from ``engine/__init__.py``. These tests import it
directly from the module where it lives.

Two layers are covered:

    1. Structural tests: the ``_STUDY_REGISTRY`` mapping must exist, must
       contain exactly the four documented study types, and each entry must
       map one-to-one to the correct typed method name with the correct
       required-kwargs tuple.

    2. Semantic tests: the validation behavior exposed through the public
       ``run_study`` API must match the documented contract exactly
       (exception types, exception messages, and defaults). These tests
       run against the public API so they pass whether or not the registry
       exists yet — they are the contract the refactor must satisfy.

The behavioral-equivalence tests live in
``test_run_study_behavioral_equivalence.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add project root to sys.path so the ``engine`` package resolves identically
# whether the test is run from ``tests/`` or the root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from engine.engine import PowerSystemEngine  # noqa: E402

# The registry is module-private. Import it directly from engine.engine.
# If the refactor has not been applied yet, the symbol does not exist and
# the structural tests are skipped (the semantic tests still run against
# the public API).
try:
    from engine.engine import _STUDY_REGISTRY  # noqa: E402
except ImportError:  # pragma: no cover - exercised only pre-refactor
    _STUDY_REGISTRY = None


# ---------------------------------------------------------------------------
# Documented contract (single source of truth for the tests)
# ---------------------------------------------------------------------------
# study_type -> (required_kwargs, method_name)
EXPECTED_REGISTRY: dict[str, tuple[tuple[str, ...], str]] = {
    "load_flow": ((), "run_load_flow"),
    "short_circuit": (("bus_id",), "run_fault_analysis"),
    "protection_coordination": (
        ("upstream_relay_id", "downstream_relay_id", "fault_currents"),
        "run_protection_coordination",
    ),
    "arc_flash": (
        ("voltage_kv", "bolted_fault_current_ka", "arc_duration_sec", "working_distance_mm"),
        "run_arc_flash",
    ),
}

# Documented optional-kwarg defaults for arc_flash (mirrors the current
# kwargs.get(...) fallbacks in run_study).
ARC_FLASH_OPTIONAL_DEFAULTS: dict[str, object] = {
    "electrode_config": "VCB",
    "enclosure_type": "box",
    "enclosure_width_mm": 508.0,
    "enclosure_height_mm": 508.0,
    "enclosure_depth_mm": 508.0,
}


# ---------------------------------------------------------------------------
# Structural tests — the registry itself
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    _STUDY_REGISTRY is None,
    reason="_STUDY_REGISTRY not yet implemented in engine/engine.py",
)
class TestStudyRegistryStructure:
    """The registry must be a module-level dict mapping each study_type to
    (required_kwargs, method_name)."""

    def test_registry_is_dict(self) -> None:
        assert isinstance(_STUDY_REGISTRY, dict)

    def test_registry_has_exactly_four_study_types(self) -> None:
        assert set(_STUDY_REGISTRY.keys()) == {
            "load_flow",
            "short_circuit",
            "protection_coordination",
            "arc_flash",
        }

    def test_registry_matches_documented_spec(self) -> None:
        """Every entry must match the documented (required_kwargs, method_name)
        spec exactly — this is the one-to-one mapping contract."""
        assert _STUDY_REGISTRY == EXPECTED_REGISTRY

    def test_each_entry_is_required_kwargs_tuple_plus_method_name(self) -> None:
        for study_type, (required, method_name) in _STUDY_REGISTRY.items():
            assert isinstance(required, tuple), (
                f"{study_type}: required_kwargs must be a tuple, got {type(required).__name__}"
            )
            assert all(isinstance(k, str) for k in required), (
                f"{study_type}: required_kwargs must contain only str"
            )
            assert isinstance(method_name, str), (
                f"{study_type}: method_name must be a str, got {type(method_name).__name__}"
            )

    def test_method_names_resolve_on_engine_instance(self) -> None:
        """Each method_name must resolve to a callable bound method on a
        PowerSystemEngine instance (the registry stores names, not bound
        methods, to avoid module-level binding to self)."""
        engine = PowerSystemEngine()
        for study_type, (_required, method_name) in _STUDY_REGISTRY.items():
            handler = getattr(engine, method_name, None)
            assert callable(handler), (
                f"{study_type}: {method_name!r} is not a callable method on PowerSystemEngine"
            )

    def test_required_kwargs_match_documented_validation(self) -> None:
        """The required-kwargs tuples must mirror the current inline
        validation exactly."""
        assert _STUDY_REGISTRY["load_flow"][0] == ()
        assert _STUDY_REGISTRY["short_circuit"][0] == ("bus_id",)
        assert _STUDY_REGISTRY["protection_coordination"][0] == (
            "upstream_relay_id",
            "downstream_relay_id",
            "fault_currents",
        )
        assert _STUDY_REGISTRY["arc_flash"][0] == (
            "voltage_kv",
            "bolted_fault_current_ka",
            "arc_duration_sec",
            "working_distance_mm",
        )


# ---------------------------------------------------------------------------
# Semantic tests — validation behavior via the public API
# ---------------------------------------------------------------------------
class TestRunStudyValidationSemantics:
    """These tests pin the validation behavior of the public run_study API.
    They run against the current implementation AND the refactored one, so
    they are the contract the refactor must preserve."""

    def test_unknown_study_type_raises_exact_message(self) -> None:
        engine = PowerSystemEngine()
        with pytest.raises(ValueError, match=r"^Unsupported study type: bogus$"):
            engine.run_study(study_type="bogus")

    def test_short_circuit_missing_bus_id_raises_exact_message(self) -> None:
        engine = PowerSystemEngine()
        with pytest.raises(ValueError, match=r"^bus_id must be provided for fault study$"):
            engine.run_study(study_type="short_circuit")

    def test_protection_coordination_missing_required_raises_exact_message(self) -> None:
        engine = PowerSystemEngine()
        expected = (
            "upstream_relay_id, downstream_relay_id, and fault_currents "
            "must be provided"
        )
        with pytest.raises(ValueError, match=expected):
            engine.run_study(study_type="protection_coordination")

    def test_arc_flash_missing_required_raises_exact_message(self) -> None:
        engine = PowerSystemEngine()
        expected = (
            r"arc_flash requires: voltage_kv, bolted_fault_current_ka, "
            r"arc_duration_sec, working_distance_mm "
            r"\(missing: voltage_kv, bolted_fault_current_ka, "
            r"arc_duration_sec, working_distance_mm\)"
        )
        with pytest.raises(ValueError, match=expected):
            engine.run_study(study_type="arc_flash")

    def test_arc_flash_optional_kwargs_fall_back_to_documented_defaults(self) -> None:
        """When optional arc_flash kwargs are omitted, the result must reflect
        the documented defaults (electrode_config='VCB', enclosure_type='box',
        508 mm cube)."""
        engine = PowerSystemEngine()
        result = engine.run_study(
            study_type="arc_flash",
            voltage_kv=4.16,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.183,
            working_distance_mm=610.0,
        )
        assert result["electrode_configuration"] == ARC_FLASH_OPTIONAL_DEFAULTS["electrode_config"]
        assert result["enclosure_type"] == ARC_FLASH_OPTIONAL_DEFAULTS["enclosure_type"]
        assert result["voltage_kv"] == pytest.approx(4.16)
        assert result["bolted_fault_current_ka"] == pytest.approx(20.0)
        assert result["arc_duration_sec"] == pytest.approx(0.183)
        assert result["working_distance_mm"] == pytest.approx(610.0)

    def test_arc_flash_optional_kwargs_override_defaults(self) -> None:
        """Explicit optional kwargs must override the defaults."""
        engine = PowerSystemEngine()
        result = engine.run_study(
            study_type="arc_flash",
            voltage_kv=4.16,
            bolted_fault_current_ka=20.0,
            arc_duration_sec=0.183,
            working_distance_mm=610.0,
            electrode_config="VCBB",
            enclosure_type="open",
            enclosure_width_mm=600.0,
            enclosure_height_mm=600.0,
            enclosure_depth_mm=600.0,
        )
        assert result["electrode_configuration"] == "VCBB"
        assert result["enclosure_type"] == "open"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
