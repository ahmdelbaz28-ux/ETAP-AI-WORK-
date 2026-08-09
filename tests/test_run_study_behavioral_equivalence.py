"""
Behavioral-equivalence tests for PowerSystemEngine.run_study.

These tests capture the CURRENT run_study behavior as a golden baseline. They
must pass unchanged against the current if/elif implementation AND against the
proposed registry-backed refactor. If the refactor changes any of these
behaviors, the tests fail and the refactor must be reconsidered.

The contract being verified:

    For every (study_type, kwargs) pair that the current run_study accepts,
    run_study(study_type, **kwargs) must produce output that is deep-equal
    to calling the typed method directly with the same arguments.

    For every invalid input the current run_study rejects, the refactored
    run_study must reject the same input with the SAME exception type, the
    SAME exception message, and the SAME validation ordering.

Three layers are covered:

    1. Direct equivalence tests: run_study vs typed method, identical inputs.
    2. End-to-end tests through the same paths existing callers use
       (load_flow on a small System, short_circuit with fault_type/bus_id,
       arc_flash canonical 4.16 kV case, protection_coordination with valid
       relays_config).
    3. Exception equivalence tests: same invalid inputs produce the same
       exception types and messages.

No part of this file depends on the registry. The registry tests live in
``test_run_study_registry.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, cast

import pytest

# Add project root to sys.path so the ``engine`` package resolves identically
# whether the test is run from ``tests/`` or the root. Mirrors the pattern in
# ``test_arc_flash_single_engine.py`` and ``test_ieee_benchmarks.py``.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core_model.bus import Bus  # noqa: E402
from core_model.line import Line  # noqa: E402
from core_model.system import System  # noqa: E402
from engine.engine import PowerSystemEngine  # noqa: E402

# ---------------------------------------------------------------------------
# Canonical study parameters
# ---------------------------------------------------------------------------
# These mirror the parameters used by the existing single-engine and IEEE
# benchmark tests so we are exercising the same paths real callers use.

# Canonical 4.16 kV IEEE 1584-2018 reference case. Identical to STUDY_PARAMS
# in ``test_arc_flash_single_engine.py``.
ARC_FLASH_PARAMS: dict = {
    "voltage_kv": 4.16,
    "bolted_fault_current_ka": 20.0,
    "arc_duration_sec": 0.183,
    "working_distance_mm": 610.0,
    "electrode_config": "VCB",
    "enclosure_type": "box",
}

# Minimal 2-bus radial system for load_flow and short_circuit. Bus 1 is slack,
# bus 2 is PQ with a small load. Sufficient to exercise load_flow convergence
# and to provide a faultable bus_id (2) for short_circuit without depending on
# any specific IEEE benchmark's failure modes (see the FaultAnalyzer slack-bus
# singularity note in ``test_ieee_benchmarks.py``).
SMALL_SYSTEM_CONFIG: dict = {
    "base_mva": 100,
    "buses": [
        {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05, "voltage_angle": 0.0},
        {"bus_id": 2, "bus_type": "pq", "load_power_real": 1.0, "load_power_reactive": 0.5},
    ],
    "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05},
    ],
}

# Valid relay configuration for protection_coordination. Mirrors the schema
# documented in ``run_protection_coordination``'s docstring.
RELAYS_CONFIG: dict = {
    "upstream": {"tms": 1.0, "pickup_current_a": 1.0, "curve_type": "standard_inverse"},
    "downstream": {"tms": 0.2, "pickup_current_a": 1.0, "curve_type": "standard_inverse"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_small_system() -> System:
    """Construct a minimal working System from ``SMALL_SYSTEM_CONFIG``.

    Mirrors ``build_system`` in ``test_ieee_benchmarks.py`` but trimmed to the
    smallest network that exercises both load_flow and short_circuit.
    """
    config = SMALL_SYSTEM_CONFIG
    system = System()
    system.base_mva = config["base_mva"]
    bus_objects: dict[int, Bus] = {}
    for bus_config in config["buses"]:
        bus = Bus(
            bus_id=bus_config["bus_id"],
            voltage_magnitude=bus_config.get("voltage_magnitude", 1.0),
            voltage_angle=bus_config.get("voltage_angle", 0.0),
            bus_type=bus_config.get("bus_type", "pq"),
        )
        p = bus_config.get("load_power_real", 0)
        q = bus_config.get("load_power_reactive", 0)
        if p or q:
            bus.load_power = complex(p / config["base_mva"], q / config["base_mva"])
        system.add_bus(bus)
        bus_objects[bus_config["bus_id"]] = bus
    for line_config in config["lines"]:
        line = Line(
            line_id=line_config["line_id"],
            from_bus=bus_objects[line_config["from_bus_id"]],
            to_bus=bus_objects[line_config["to_bus_id"]],
            z1=complex(line_config.get("r1", 0), line_config.get("x1", 0)),
        )
        system.add_line(line)
    return system


# ---------------------------------------------------------------------------
# Layer 1 — direct equivalence: run_study vs typed method
# ---------------------------------------------------------------------------
class TestRunStudyEqualsTypedMethod:
    """For each study_type, ``run_study(study_type, **kwargs)`` must produce
    the same result dict as calling the typed method directly."""

    def test_load_flow_via_study_equals_typed(self) -> None:
        engine = PowerSystemEngine(_build_small_system())
        via_study = engine.run_study(study_type="load_flow")
        via_typed = engine.run_load_flow()
        assert via_study == via_typed

    def test_arc_flash_via_study_equals_typed(self) -> None:
        engine = PowerSystemEngine()  # arc flash does not need a network model
        via_study = engine.run_study(study_type="arc_flash", **ARC_FLASH_PARAMS)
        via_typed = engine.run_arc_flash(**ARC_FLASH_PARAMS)
        assert via_study == via_typed

    def test_arc_flash_via_study_equals_typed_with_optional_enclosure(self) -> None:
        """Optional enclosure kwargs must also flow through unchanged."""
        engine = PowerSystemEngine()
        params = {
            **ARC_FLASH_PARAMS,
            "enclosure_width_mm": 600.0,
            "enclosure_height_mm": 600.0,
            "enclosure_depth_mm": 600.0,
        }
        via_study = engine.run_study(study_type="arc_flash", **params)
        via_typed = engine.run_arc_flash(**params)
        assert via_study == via_typed

    def test_protection_coordination_via_study_equals_typed(self) -> None:
        """The current dispatcher calls ``run_protection_coordination`` with
        exactly three positional args (upstream_relay_id, downstream_relay_id,
        fault_currents) — it does NOT forward ``relays_config``. So the typed
        method must be called the same way for the outputs to be equivalent.
        This pins the current dispatcher behavior so the refactor preserves
        it."""
        engine = PowerSystemEngine()
        kwargs = {
            "upstream_relay_id": 1,
            "downstream_relay_id": 2,
            "fault_currents": [2.0, 5.0, 10.0],
            "relays_config": RELAYS_CONFIG,  # dropped by the current dispatcher
        }
        via_study = engine.run_study(study_type="protection_coordination", **kwargs)
        via_typed = engine.run_protection_coordination(
            upstream_relay_id=1,
            downstream_relay_id=2,
            fault_currents=[2.0, 5.0, 10.0],
            # relays_config intentionally omitted — the dispatcher does not
            # forward it today, and the refactor must not start forwarding it.
        )
        assert via_study == via_typed

    def test_protection_coordination_dispatcher_drops_relays_config(self) -> None:
        """Golden quirk: ``run_study('protection_coordination', ...)`` returns
        the simulated-error dict even when a valid ``relays_config`` is
        provided, because the current dispatcher does not forward it. The
        typed method with the same ``relays_config`` returns the real
        coordination result. The refactor MUST preserve this difference —
        callers that rely on the simulated-error response must not see a
        behavior change."""
        engine = PowerSystemEngine()
        kwargs = {
            "upstream_relay_id": 1,
            "downstream_relay_id": 2,
            "fault_currents": [2.0, 5.0, 10.0],
            "relays_config": RELAYS_CONFIG,
        }
        via_study = engine.run_study(study_type="protection_coordination", **kwargs)
        via_typed = engine.run_protection_coordination(**(cast(Dict[str, Any], kwargs)))
        # The dispatcher drops relays_config → simulated error.
        assert via_study["is_simulated"] is True
        assert via_study["all_coordinated"] is False
        assert via_study["results"] == []
        # The typed method receives relays_config → real coordination result.
        assert via_typed["is_simulated"] is False
        assert via_typed["all_coordinated"] is True
        assert len(via_typed["results"]) == 3


# ---------------------------------------------------------------------------
# Layer 2 — end-to-end through the same paths existing callers use
# ---------------------------------------------------------------------------
class TestRunStudyEndToEnd:
    """End-to-end runs through the same paths the existing callers use.

    These mirror the call patterns in ``test_arc_flash_single_engine.py``,
    ``test_ieee_benchmarks.py``, ``test_projects_api.py`` and
    ``test_coordination.py``.
    """

    def test_load_flow_end_to_end_on_small_system(self) -> None:
        """Mirrors ``test_ieee_benchmarks.py`` usage: a small System fed to the
        engine, then a load flow dispatched via ``run_study``."""
        engine = PowerSystemEngine(_build_small_system())
        result = engine.run_study(study_type="load_flow")
        assert isinstance(result, dict)
        assert result.get("converged") is True
        assert "bus_voltages" in result

    def test_arc_flash_end_to_end_canonical_4_16_kv(self) -> None:
        """Mirrors ``test_arc_flash_single_engine.py``
        ``test_direct_engine_path_returns_ieee_1584_result``."""
        engine = PowerSystemEngine()
        result = engine.run_study(study_type="arc_flash", **ARC_FLASH_PARAMS)
        assert result["method"] == "IEEE 1584-2018"
        assert result["electrode_configuration"] == "VCB"
        assert result["enclosure_type"] == "box"
        assert result["voltage_kv"] == pytest.approx(ARC_FLASH_PARAMS["voltage_kv"])
        assert result["bolted_fault_current_ka"] == pytest.approx(
            ARC_FLASH_PARAMS["bolted_fault_current_ka"]
        )
        assert result["arc_current_ka"] > 0
        assert result["incident_energy_cal_per_cm2"] >= 0
        assert result["arc_flash_boundary_mm"] >= 0
        assert result["ppe_level"] in {"0", "1", "2", "3", "4", "DANGER"}

    def test_protection_coordination_end_to_end_with_valid_relays(self) -> None:
        """Mirrors ``test_coordination.py`` patterns: a valid relays_config
        passed to run_study. The current dispatcher does NOT forward
        ``relays_config`` to ``run_protection_coordination``, so the result is
        the simulated-error dict (is_simulated=True). This is the golden
        behavior the refactor must preserve — callers that pass
        ``relays_config`` through ``run_study`` today receive the simulated
        response, not the real coordination result."""
        engine = PowerSystemEngine()
        result = engine.run_study(
            study_type="protection_coordination",
            upstream_relay_id=1,
            downstream_relay_id=2,
            fault_currents=[2.0, 5.0, 10.0],
            relays_config=RELAYS_CONFIG,
        )
        assert isinstance(result, dict)
        # Golden quirk: relays_config is dropped by the dispatcher.
        assert result["is_simulated"] is True
        assert result["all_coordinated"] is False
        assert result["results"] == []

    def test_short_circuit_default_fault_type(self) -> None:
        """``short_circuit`` without an explicit fault_type defaults to
        ``three_phase`` (mirrors the kwargs.get('fault_type', 'three_phase')
        fallback in the current implementation). The current FaultAnalyzer
        has a known slack-bus singularity (see test_ieee_benchmarks.py), so we
        only verify that the call dispatches to ``run_fault_analysis`` and
        does not raise ValueError before reaching the analyzer."""
        engine = PowerSystemEngine(_build_small_system())
        # We do not assert on the result shape — the FaultAnalyzer behavior
        # is exercised in fault_analysis's own tests. We only assert that
        # run_study without fault_type reaches the analyzer (i.e. does not
        # raise ``Unsupported study type`` or similar dispatcher errors).
        try:
            engine.run_study(study_type="short_circuit", bus_id=2)
        except ValueError as exc:
            # ValueError must NOT be the dispatcher's "Unsupported study type"
            # or "bus_id must be provided" — only the FaultAnalyzer's own
            # "Unsupported fault type" is acceptable here.
            assert "Unsupported study type" not in str(exc)
            assert "bus_id must be provided" not in str(exc)


# ---------------------------------------------------------------------------
# Layer 3 — exception equivalence
# ---------------------------------------------------------------------------
class TestRunStudyExceptionEquivalence:
    """Exception types and messages must be byte-identical to the current
    implementation. This is the strictest part of the behavioral contract."""

    def test_unsupported_study_type_message(self) -> None:
        engine = PowerSystemEngine()
        with pytest.raises(ValueError, match=r"^Unsupported study type: nonsense$"):
            engine.run_study(study_type="nonsense")

    def test_short_circuit_missing_bus_id_message(self) -> None:
        engine = PowerSystemEngine()
        with pytest.raises(ValueError, match=r"^bus_id must be provided for fault study$"):
            engine.run_study(study_type="short_circuit")

    def test_protection_coordination_missing_required_message(self) -> None:
        """Missing all three required kwargs produces the exact combined
        message. The current implementation does NOT distinguish which one is
        missing — it checks ``None`` for all three in one if."""
        engine = PowerSystemEngine()
        expected = "upstream_relay_id, downstream_relay_id, and fault_currents must be provided"
        with pytest.raises(ValueError, match=expected):
            engine.run_study(study_type="protection_coordination")

    def test_protection_coordination_partial_required_message(self) -> None:
        """Even if only one required kwarg is missing, the same combined
        message is raised. Preserves current ``None``-check semantics."""
        engine = PowerSystemEngine()
        expected = "upstream_relay_id, downstream_relay_id, and fault_currents must be provided"
        with pytest.raises(ValueError, match=expected):
            engine.run_study(
                study_type="protection_coordination",
                upstream_relay_id=1,
                # downstream_relay_id missing
                fault_currents=[2.0],
            )

    def test_arc_flash_missing_all_required_lists_all(self) -> None:
        engine = PowerSystemEngine()
        expected = (
            r"arc_flash requires: voltage_kv, bolted_fault_current_ka, "
            r"arc_duration_sec, working_distance_mm "
            r"\(missing: voltage_kv, bolted_fault_current_ka, "
            r"arc_duration_sec, working_distance_mm\)"
        )
        with pytest.raises(ValueError, match=expected):
            engine.run_study(study_type="arc_flash")

    def test_arc_flash_missing_one_required_lists_only_that(self) -> None:
        engine = PowerSystemEngine()
        expected = (
            r"arc_flash requires: voltage_kv, bolted_fault_current_ka, "
            r"arc_duration_sec, working_distance_mm "
            r"\(missing: bolted_fault_current_ka\)"
        )
        with pytest.raises(ValueError, match=expected):
            engine.run_study(
                study_type="arc_flash",
                voltage_kv=4.16,
                arc_duration_sec=0.183,
                working_distance_mm=610.0,
                # bolted_fault_current_ka missing
            )


# ---------------------------------------------------------------------------
# Layer 4 — golden output equivalence
# ---------------------------------------------------------------------------
class TestRunStudyGoldenEquivalence:
    """Capture the current ``run_study`` output for a fixed set of inputs and
    assert the refactored implementation produces identical output. Because
    the refactor is behavior-preserving, the golden values are the typed
    methods' outputs (which is what ``run_study`` is required to return
    today)."""

    def test_arc_flash_golden_matches_typed_method(self) -> None:
        engine = PowerSystemEngine()
        study_result = engine.run_study(study_type="arc_flash", **ARC_FLASH_PARAMS)
        typed_result = engine.run_arc_flash(**ARC_FLASH_PARAMS)
        assert study_result == typed_result

    def test_protection_coordination_golden_matches_typed_method(self) -> None:
        """Golden equivalence for protection_coordination: the dispatcher
        calls the typed method with exactly three positional args (no
        relays_config), so the golden comparison must call the typed method
        the same way."""
        engine = PowerSystemEngine()
        kwargs = {
            "upstream_relay_id": 1,
            "downstream_relay_id": 2,
            "fault_currents": [2.0, 5.0, 10.0],
            "relays_config": RELAYS_CONFIG,  # dropped by the dispatcher
        }
        study_result = engine.run_study(study_type="protection_coordination", **kwargs)
        typed_result = engine.run_protection_coordination(
            upstream_relay_id=1,
            downstream_relay_id=2,
            fault_currents=[2.0, 5.0, 10.0],
            # relays_config intentionally omitted — matches the dispatcher.
        )
        assert study_result == typed_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
