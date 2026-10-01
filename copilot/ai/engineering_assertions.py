"""
Engineering Assertion Layer — Deterministic Validation for AI Outputs
=====================================================================

Security Fix V-04: When the prompt fallback system falls back to a
less-capable model or a hardcoded safety-net prompt, the AI's output
may look syntactically valid but contain engineering-unsafe values.

This module provides deterministic, script-based checks that validate
the numerical correctness of AI-generated engineering outputs BEFORE
they are shown to the user. This is NOT a prompt-level check — it is
a computational verification layer that runs independently of the AI.

Checks include:
- Voltage range sanity (IEEE C84.1 Range A/B)
- Short-circuit current magnitude consistency (IEC 60909)
- Trip time physical plausibility (IEC 60255 curves)
- Arc flash energy bounds (IEEE 1584)
- Cable sizing ampacity verification (IEC 60364)
- Protection coordination selectivity (IEEE C37.90)

Reference: docs/adr/0003-three-tier-prompt-fallback.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AssertionSeverity(Enum):
    """Severity level for assertion failures."""

    INFO = "info"  # Informational check that passed
    WARNING = "warning"  # Suspicious but not necessarily wrong
    CRITICAL = "critical"  # Physically impossible or dangerous
    FATAL = "fatal"  # Will cause injury/death if acted upon


@dataclass
class AssertionResult:
    """Result of a single engineering assertion check."""

    check_name: str
    passed: bool
    severity: AssertionSeverity = AssertionSeverity.INFO
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_name": self.check_name,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class AssertionReport:
    """Consolidated report produced by EngineeringAssertionLayer.validate()."""

    passed: bool
    failures: list[AssertionResult] = field(default_factory=list)
    warnings: list[AssertionResult] = field(default_factory=list)
    all_results: list[AssertionResult] = field(default_factory=list)
    has_critical_failures: bool = False
    has_any_failures: bool = False
    summary: dict[str, Any] = field(default_factory=dict)

    def __iter__(self):
        return iter(self.all_results)

    def __len__(self):
        return len(self.all_results)


class EngineeringAssertionLayer:
    """
    Deterministic assertion layer for validating AI-generated engineering outputs.

    This layer is designed to be called AFTER the AI model produces a response,
    especially when the response comes from a fallback model or safety-net prompt.
    It checks the numerical outputs against physical constraints and engineering
    standards, rejecting results that are physically impossible or dangerous.

    Usage:
        layer = EngineeringAssertionLayer()
        results = layer.validate_short_circuit_results(fault_currents={...})
        if not all(r.passed for r in results):
            # Reject or flag the AI output
    """

    # IEEE C84.1 Range A voltage limits (per-unit, typical 11kV system)
    VOLTAGE_PU_MIN_RANGE_A = 0.95
    VOLTAGE_PU_MAX_RANGE_A = 1.05
    VOLTAGE_PU_MIN_RANGE_B = 0.91
    VOLTAGE_PU_MAX_RANGE_B = 1.08

    # Physical constraints for short circuit currents
    MAX_FAULT_CURRENT_KA = 200.0  # No practical system exceeds 200 kA
    MIN_FAULT_CURRENT_A = 0.001  # Below 1 mA is measurement noise

    # IEC 60255 trip time bounds
    MIN_TRIP_TIME_S = 0.005  # 5 ms minimum (instantaneous element)
    MAX_TRIP_TIME_S = 300.0  # 5 minutes maximum (long-time element)

    # IEEE 1584 arc flash energy bounds
    MAX_INCIDENT_ENERGY_CAL_CM2 = 100.0  # Realistic upper bound
    MIN_ARC_FLASH_BOUNDARY_MM = 300.0  # Minimum safe boundary

    # Cable ampacity bounds (IEC 60364)
    MAX_CABLE_AMPERAGE = 2000.0  # No single cable exceeds 2000A
    MIN_CABLE_SIZE_MM2 = 1.5  # Minimum practical cable size

    def __init__(self, strict_mode: bool = False):
        """
        Initialize the assertion layer.

        Parameters
        ----------
        strict_mode : bool
            If True, WARNING-level failures also cause rejection.
            If False, only CRITICAL and FATAL failures cause rejection (default).
        """
        self.strict_mode = strict_mode
        self._results: list[AssertionResult] = []

    def validate_voltage_results(
        self,
        bus_voltages: dict[str, float],
        nominal_voltage_kv: float = 11.0,
    ) -> list[AssertionResult]:
        """
        Validate bus voltage magnitudes against IEEE C84.1.

        Checks that all bus voltages are within Range B (absolute minimum)
        and flags Range A violations as warnings.

        Parameters
        ----------
        bus_voltages : dict
            Mapping of bus_id to voltage in kV.
        nominal_voltage_kv : float
            Nominal system voltage in kV.

        Returns
        -------
        list[AssertionResult]
            Results for each bus voltage check.
        """
        results = []
        for bus_id, voltage_kv in bus_voltages.items():
            if nominal_voltage_kv <= 0:
                results.append(
                    AssertionResult(
                        check_name="voltage_range",
                        passed=False,
                        severity=AssertionSeverity.CRITICAL,
                        message=f"Invalid nominal voltage {nominal_voltage_kv} kV for bus {bus_id}",
                        details={"bus_id": bus_id, "voltage_kv": voltage_kv},
                    )
                )
                continue

            if isinstance(voltage_kv, dict):
                re_v = float(voltage_kv.get("re", voltage_kv.get("real", 0.0)))
                im_v = float(voltage_kv.get("im", voltage_kv.get("imag", 0.0)))
                mag = (re_v**2 + im_v**2) ** 0.5
            elif isinstance(voltage_kv, complex) or hasattr(voltage_kv, "imag"):
                mag = float(abs(voltage_kv))
            else:
                try:
                    mag = abs(float(voltage_kv))
                except (ValueError, TypeError):
                    mag = 0.0

            voltage_pu = mag / nominal_voltage_kv

            # Range B check (hard limit)
            if voltage_pu < self.VOLTAGE_PU_MIN_RANGE_B or voltage_pu > self.VOLTAGE_PU_MAX_RANGE_B:
                results.append(
                    AssertionResult(
                        check_name="voltage_range_b",
                        passed=False,
                        severity=AssertionSeverity.CRITICAL,
                        message=(
                            f"Bus {bus_id} voltage {voltage_pu:.3f} pu is outside "
                            f"IEEE C84.1 Range B ({self.VOLTAGE_PU_MIN_RANGE_B:.2f}-"
                            f"{self.VOLTAGE_PU_MAX_RANGE_B:.2f} pu)"
                        ),
                        details={
                            "bus_id": bus_id,
                            "voltage_kv": voltage_kv,
                            "voltage_pu": voltage_pu,
                        },
                    )
                )
            # Range A check (warning)
            elif (
                voltage_pu < self.VOLTAGE_PU_MIN_RANGE_A or voltage_pu > self.VOLTAGE_PU_MAX_RANGE_A
            ):
                results.append(
                    AssertionResult(
                        check_name="voltage_range_a",
                        passed=not self.strict_mode,
                        severity=AssertionSeverity.WARNING,
                        message=(
                            f"Bus {bus_id} voltage {voltage_pu:.3f} pu is outside "
                            f"IEEE C84.1 Range A ({self.VOLTAGE_PU_MIN_RANGE_A:.2f}-"
                            f"{self.VOLTAGE_PU_MAX_RANGE_A:.2f} pu) but within Range B"
                        ),
                        details={
                            "bus_id": bus_id,
                            "voltage_kv": voltage_kv,
                            "voltage_pu": voltage_pu,
                        },
                    )
                )
            else:
                results.append(
                    AssertionResult(
                        check_name="voltage_range",
                        passed=True,
                        message=f"Bus {bus_id} voltage {voltage_pu:.3f} pu is within Range A",
                        details={
                            "bus_id": bus_id,
                            "voltage_kv": voltage_kv,
                            "voltage_pu": voltage_pu,
                        },
                    )
                )

        self._results.extend(results)
        return results

    def validate_short_circuit_results(
        self,
        fault_currents: dict[str, float],
        max_expected_ka: float = 50.0,
    ) -> list[AssertionResult]:
        """
        Validate short-circuit current magnitudes against IEC 60909.

        Checks that fault currents are within physically plausible ranges
        and consistent with the system's maximum expected fault level.

        Parameters
        ----------
        fault_currents : dict
            Mapping of fault_id or bus_id to fault current in kA.
        max_expected_ka : float
            Maximum expected fault current for this system in kA.

        Returns
        -------
        list[AssertionResult]
            Results for each fault current check.
        """
        results = []
        for fault_id, current_ka in fault_currents.items():
            # Check absolute physical bounds
            if current_ka > self.MAX_FAULT_CURRENT_KA:
                results.append(
                    AssertionResult(
                        check_name="fault_current_absolute",
                        passed=False,
                        severity=AssertionSeverity.FATAL,
                        message=(
                            f"Fault current {current_ka:.1f} kA at {fault_id} exceeds "
                            f"physical maximum {self.MAX_FAULT_CURRENT_KA} kA"
                        ),
                        details={"fault_id": fault_id, "current_ka": current_ka},
                    )
                )
            elif current_ka < self.MIN_FAULT_CURRENT_A / 1000:
                results.append(
                    AssertionResult(
                        check_name="fault_current_minimum",
                        passed=False,
                        severity=AssertionSeverity.WARNING,
                        message=(
                            f"Fault current {current_ka:.6f} kA at {fault_id} is below "
                            f"minimum detectable threshold"
                        ),
                        details={"fault_id": fault_id, "current_ka": current_ka},
                    )
                )
            # Check consistency with system's maximum expected fault level
            elif current_ka > max_expected_ka * 1.5:
                # Allow 50% margin above expected for motor contribution, etc.
                results.append(
                    AssertionResult(
                        check_name="fault_current_consistency",
                        passed=not self.strict_mode,
                        severity=AssertionSeverity.WARNING,
                        message=(
                            f"Fault current {current_ka:.1f} kA at {fault_id} significantly "
                            f"exceeds expected maximum {max_expected_ka:.1f} kA (>{max_expected_ka * 1.5:.1f} kA)"
                        ),
                        details={
                            "fault_id": fault_id,
                            "current_ka": current_ka,
                            "max_expected_ka": max_expected_ka,
                        },
                    )
                )
            else:
                results.append(
                    AssertionResult(
                        check_name="fault_current",
                        passed=True,
                        message=f"Fault current {current_ka:.1f} kA at {fault_id} is within expected range",
                        details={"fault_id": fault_id, "current_ka": current_ka},
                    )
                )

        self._results.extend(results)
        return results

    def validate_trip_time(
        self,
        relay_id: str,
        trip_time_s: float,
        current_a: float,
        pickup_a: float,
    ) -> AssertionResult:
        """
        Validate a relay trip time against IEC 60255 physical bounds.

        A trip time that is physically impossible (too fast or too slow)
        indicates a calculation error in the AI output.

        Parameters
        ----------
        relay_id : str
            Relay identifier.
        trip_time_s : float
            Calculated trip time in seconds.
        current_a : float
            Fault current in amperes.
        pickup_a : float
            Pickup current setting in amperes.

        Returns
        -------
        AssertionResult
        """
        if trip_time_s < self.MIN_TRIP_TIME_S:
            result = AssertionResult(
                check_name="trip_time_minimum",
                passed=False,
                severity=AssertionSeverity.FATAL,
                message=(
                    f"Relay {relay_id} trip time {trip_time_s * 1000:.1f} ms is below "
                    f"physical minimum {self.MIN_TRIP_TIME_S * 1000:.1f} ms"
                ),
                details={
                    "relay_id": relay_id,
                    "trip_time_s": trip_time_s,
                    "current_a": current_a,
                    "pickup_a": pickup_a,
                },
            )
        elif trip_time_s > self.MAX_TRIP_TIME_S:
            result = AssertionResult(
                check_name="trip_time_maximum",
                passed=False,
                severity=AssertionSeverity.CRITICAL,
                message=(
                    f"Relay {relay_id} trip time {trip_time_s:.1f} s exceeds "
                    f"practical maximum {self.MAX_TRIP_TIME_S:.1f} s"
                ),
                details={
                    "relay_id": relay_id,
                    "trip_time_s": trip_time_s,
                    "current_a": current_a,
                    "pickup_a": pickup_a,
                },
            )
        elif current_a > pickup_a and trip_time_s > 100:
            # Current is above pickup but trip time is very long — suspicious
            result = AssertionResult(
                check_name="trip_time_consistency",
                passed=not self.strict_mode,
                severity=AssertionSeverity.WARNING,
                message=(
                    f"Relay {relay_id} trip time {trip_time_s:.1f} s is unusually long "
                    f"for current {current_a:.1f} A >> pickup {pickup_a:.1f} A"
                ),
                details={
                    "relay_id": relay_id,
                    "trip_time_s": trip_time_s,
                    "current_a": current_a,
                    "pickup_a": pickup_a,
                },
            )
        else:
            result = AssertionResult(
                check_name="trip_time",
                passed=True,
                message=f"Relay {relay_id} trip time {trip_time_s:.3f} s is within physical bounds",
                details={"relay_id": relay_id, "trip_time_s": trip_time_s},
            )

        self._results.append(result)
        return result

    def validate_coordination_selectivity(
        self,
        upstream_relay: str,
        downstream_relay: str,
        upstream_trip_s: float,
        downstream_trip_s: float,
        min_margin_s: float = 0.2,
        fault_current_a: float = 0.0,
    ) -> AssertionResult:
        """Validate protection selectivity between upstream and downstream devices."""
        margin = upstream_trip_s - downstream_trip_s
        if margin < 0:
            result = AssertionResult(
                check_name="coordination_selectivity_violation",
                passed=False,
                severity=AssertionSeverity.CRITICAL,
                message=(
                    f"Non-selective trip: upstream {upstream_relay} ({upstream_trip_s:.3f} s) "
                    f"trips faster than or simultaneously with downstream {downstream_relay} ({downstream_trip_s:.3f} s)"
                ),
                details={
                    "upstream_relay": upstream_relay,
                    "downstream_relay": downstream_relay,
                    "upstream_trip_s": upstream_trip_s,
                    "downstream_trip_s": downstream_trip_s,
                    "margin_s": margin,
                    "fault_current_a": fault_current_a,
                },
            )
        elif margin < min_margin_s:
            result = AssertionResult(
                check_name="coordination_selectivity_margin",
                passed=not self.strict_mode,
                severity=AssertionSeverity.WARNING,
                message=(
                    f"Coordination time interval {margin:.3f} s between {upstream_relay} and "
                    f"{downstream_relay} is below recommended CTI {min_margin_s:.3f} s"
                ),
                details={
                    "upstream_relay": upstream_relay,
                    "downstream_relay": downstream_relay,
                    "upstream_trip_s": upstream_trip_s,
                    "downstream_trip_s": downstream_trip_s,
                    "margin_s": margin,
                },
            )
        else:
            result = AssertionResult(
                check_name="coordination_selectivity",
                passed=True,
                message=f"Coordination OK between {upstream_relay} and {downstream_relay} (CTI = {margin:.3f} s)",
                details={
                    "upstream_relay": upstream_relay,
                    "downstream_relay": downstream_relay,
                    "margin_s": margin,
                },
            )
        self._results.append(result)
        return result

    def validate_arc_flash_results(
        self,
        incident_energy_cal_cm2: dict[str, float],
        arc_flash_boundaries_mm: dict[str, float] | None = None,
    ) -> list[AssertionResult]:
        """
        Validate arc flash results against IEEE 1584 bounds.

        Parameters
        ----------
        incident_energy_cal_cm2 : dict
            Mapping of bus_id to incident energy in cal/cm2.
        arc_flash_boundaries_mm : dict, optional
            Mapping of bus_id to arc flash boundary in mm.

        Returns
        -------
        list[AssertionResult]
        """
        results = []
        for bus_id, energy in incident_energy_cal_cm2.items():
            if energy < 0:
                results.append(
                    AssertionResult(
                        check_name="arc_flash_energy_negative",
                        passed=False,
                        severity=AssertionSeverity.FATAL,
                        message=f"Negative incident energy {energy:.2f} cal/cm2 at {bus_id} is physically impossible",
                        details={"bus_id": bus_id, "energy_cal_cm2": energy},
                    )
                )
            elif energy > self.MAX_INCIDENT_ENERGY_CAL_CM2:
                results.append(
                    AssertionResult(
                        check_name="arc_flash_energy_upper",
                        passed=False,
                        severity=AssertionSeverity.CRITICAL,
                        message=(
                            f"Incident energy {energy:.1f} cal/cm2 at {bus_id} exceeds "
                            f"realistic upper bound {self.MAX_INCIDENT_ENERGY_CAL_CM2} cal/cm2"
                        ),
                        details={"bus_id": bus_id, "energy_cal_cm2": energy},
                    )
                )
            else:
                results.append(
                    AssertionResult(
                        check_name="arc_flash_energy",
                        passed=True,
                        message=f"Incident energy {energy:.2f} cal/cm2 at {bus_id} is within bounds",
                        details={"bus_id": bus_id, "energy_cal_cm2": energy},
                    )
                )

        if arc_flash_boundaries_mm:
            for bus_id, boundary_mm in arc_flash_boundaries_mm.items():
                if boundary_mm < self.MIN_ARC_FLASH_BOUNDARY_MM:
                    results.append(
                        AssertionResult(
                            check_name="arc_flash_boundary",
                            passed=False,
                            severity=AssertionSeverity.CRITICAL,
                            message=(
                                f"Arc flash boundary {boundary_mm:.0f} mm at {bus_id} is below "
                                f"minimum safe distance {self.MIN_ARC_FLASH_BOUNDARY_MM:.0f} mm"
                            ),
                            details={"bus_id": bus_id, "boundary_mm": boundary_mm},
                        )
                    )

        self._results.extend(results)
        return results

    def validate_cable_sizing(
        self,
        cable_loads_a: dict[str, float],
        cable_ampacities_a: dict[str, float],
    ) -> list[AssertionResult]:
        """
        Validate cable sizing against ampacity requirements (IEC 60364).

        Each cable's ampacity must be at least equal to the load current.

        Parameters
        ----------
        cable_loads_a : dict
            Mapping of cable_id to load current in amperes.
        cable_ampacities_a : dict
            Mapping of cable_id to rated ampacity in amperes.

        Returns
        -------
        list[AssertionResult]
        """
        results = []
        for cable_id, load_a in cable_loads_a.items():
            ampacity_a = cable_ampacities_a.get(cable_id)
            if ampacity_a is None:
                results.append(
                    AssertionResult(
                        check_name="cable_ampacity_missing",
                        passed=False,
                        severity=AssertionSeverity.CRITICAL,
                        message=f"No ampacity data for cable {cable_id}",
                        details={"cable_id": cable_id, "load_a": load_a},
                    )
                )
                continue

            if load_a > ampacity_a:
                results.append(
                    AssertionResult(
                        check_name="cable_overload",
                        passed=False,
                        severity=AssertionSeverity.FATAL,
                        message=(
                            f"Cable {cable_id} load {load_a:.1f} A exceeds "
                            f"ampacity {ampacity_a:.1f} A — FIRE HAZARD"
                        ),
                        details={"cable_id": cable_id, "load_a": load_a, "ampacity_a": ampacity_a},
                    )
                )
            elif ampacity_a > self.MAX_CABLE_AMPERAGE:
                results.append(
                    AssertionResult(
                        check_name="cable_ampacity_unrealistic",
                        passed=False,
                        severity=AssertionSeverity.CRITICAL,
                        message=(
                            f"Cable {cable_id} ampacity {ampacity_a:.1f} A exceeds "
                            f"realistic maximum {self.MAX_CABLE_AMPERAGE:.0f} A"
                        ),
                        details={"cable_id": cable_id, "ampacity_a": ampacity_a},
                    )
                )
            else:
                results.append(
                    AssertionResult(
                        check_name="cable_sizing",
                        passed=True,
                        message=f"Cable {cable_id} sizing OK ({load_a:.1f} A <= {ampacity_a:.1f} A)",
                        details={"cable_id": cable_id, "load_a": load_a, "ampacity_a": ampacity_a},
                    )
                )

        self._results.extend(results)
        return results

    def validate(
        self,
        data: dict[str, Any],
        study_type: str,
    ) -> AssertionReport:
        """
        Validate simulation results against physical standards and engineering constraints.

        Handles canonical study types and aliases across native, ETAP, and AI pipelines.
        """
        start_idx = len(self._results)
        canonical = study_type.lower().replace("-", "_").strip()
        if canonical.startswith("etap_"):
            canonical = canonical[5:]
        alias_map = {
            "fault": "short_circuit",
            "coordination": "protection_coordination",
            "protection": "protection_coordination",
            "harmonic": "harmonic_analysis",
            "stability": "transient_stability",
            "opf": "optimal_power_flow",
            "cable": "cable_sizing",
        }
        canonical = alias_map.get(canonical, canonical)

        if canonical in ("load_flow", "optimal_power_flow"):
            if data.get("converged") is False:
                # Unconverged load flow has no valid steady-state solution to validate
                pass
            else:
                bus_voltages = data.get("bus_voltages")
                if not bus_voltages:
                    raw_buses = data.get("buses") or data.get("bus_results") or data.get("results", {}).get("buses")
                    if isinstance(raw_buses, dict):
                        bus_voltages = {}
                        for k, v in raw_buses.items():
                            if isinstance(v, dict):
                                for key in (
                                    "voltage_magnitude_pu",
                                    "vm_pu",
                                    "voltage_pu",
                                    "v_pu",
                                    "voltage_magnitude",
                                    "voltage_kv",
                                    "vm",
                                ):
                                    if key in v:
                                        try:
                                            bus_voltages[str(k)] = float(v[key])
                                            break
                                        except (TypeError, ValueError):
                                            pass
                            elif isinstance(v, (int, float)):
                                bus_voltages[str(k)] = float(v)

                if isinstance(bus_voltages, dict) and bus_voltages:
                    mags = {}
                    for k, v in bus_voltages.items():
                        if isinstance(v, dict):
                            re_v = float(v.get("re", v.get("real", 0.0)))
                            im_v = float(v.get("im", v.get("imag", 0.0)))
                            mags[str(k)] = (re_v**2 + im_v**2) ** 0.5
                        elif isinstance(v, complex) or hasattr(v, "imag"):
                            mags[str(k)] = float(abs(v))
                        else:
                            try:
                                mags[str(k)] = abs(float(v))
                            except (ValueError, TypeError):
                                mags[str(k)] = 0.0

                    nominal_kv = float(data.get("nominal_voltage_kv", data.get("base_kv", 1.0)))
                    all_pu = all(0.0 <= val <= 3.0 for val in mags.values())
                    if all_pu and nominal_kv != 1.0 and (max(mags.values()) if mags else 0) <= 2.5:
                        nominal_kv = 1.0
                    self.validate_voltage_results(mags, nominal_voltage_kv=nominal_kv)

        elif canonical in ("short_circuit", "fault_analysis"):
            fault_currents = (
                data.get("fault_currents")
                or data.get("fault_results")
                or data.get("short_circuit_currents")
                or data.get("results", {}).get("faults")
            )
            if isinstance(fault_currents, dict) and fault_currents:
                curr_ka = {}
                for k, v in fault_currents.items():
                    if isinstance(v, dict):
                        if "three_phase" in v or "line_to_ground" in v or "line_to_line" in v:
                            tp = v.get("three_phase") or {}
                            val = tp.get("fault_current_ka", tp.get("fault_current_magnitude", 0.0))
                            if not val:
                                for f_item in v.values():
                                    if isinstance(f_item, dict):
                                        cand = f_item.get("fault_current_ka", f_item.get("fault_current_b_ka", 0.0))
                                        val = max(float(val or 0.0), float(cand or 0.0))
                        else:
                            val = v.get(
                                "ik_ss_ka",
                                v.get("ik_ka", v.get("current_ka", v.get("magnitude", v.get("mag", 0.0)))),
                            )
                        try:
                            curr_ka[str(k)] = float(val)
                        except (TypeError, ValueError):
                            curr_ka[str(k)] = 0.0
                    elif isinstance(v, (int, float)):
                        curr_ka[str(k)] = float(v)
                if curr_ka:
                    max_exp = float(data.get("max_expected_ka", 50.0))
                    self.validate_short_circuit_results(curr_ka, max_expected_ka=max_exp)

        elif canonical in ("arc_flash",):
            incident_energy = data.get("incident_energy") or data.get("arc_flash_results")
            boundaries = data.get("arc_flash_boundaries") or data.get("boundaries")
            if isinstance(incident_energy, dict) and incident_energy:
                energy_cal = {}
                for k, v in incident_energy.items():
                    if isinstance(v, dict):
                        try:
                            energy_cal[str(k)] = float(
                                v.get("incident_energy_cal_cm2", v.get("energy", 0.0))
                            )
                        except (TypeError, ValueError):
                            energy_cal[str(k)] = 0.0
                    elif isinstance(v, (int, float)):
                        energy_cal[str(k)] = float(v)
                boundary_mm = None
                if isinstance(boundaries, dict):
                    boundary_mm = {}
                    for k, v in boundaries.items():
                        try:
                            boundary_mm[str(k)] = float(v)
                        except (TypeError, ValueError):
                            boundary_mm[str(k)] = 0.0
                self.validate_arc_flash_results(energy_cal, boundary_mm)

        elif canonical in ("protection_coordination",):
            relay_results = (
                data.get("relay_results") or data.get("relays") or data.get("coordination_results")
            )
            if isinstance(relay_results, list):
                for r in relay_results:
                    if isinstance(r, dict) and ("trip_time_s" in r or "trip_time" in r):
                        try:
                            self.validate_trip_time(
                                relay_id=str(r.get("relay_id", "unknown")),
                                trip_time_s=float(r.get("trip_time_s", r.get("trip_time", 0.0))),
                                current_a=float(r.get("current_a", r.get("current", 0.0))),
                                pickup_a=float(r.get("pickup_a", r.get("pickup", 0.0))),
                            )
                        except (TypeError, ValueError):
                            pass
            selectivity_checks = data.get("selectivity_checks") or data.get("selectivity_pairs")
            if isinstance(selectivity_checks, list):
                for pair in selectivity_checks:
                    if isinstance(pair, dict):
                        try:
                            self.validate_coordination_selectivity(
                                upstream_relay=str(pair.get("upstream_relay", "up")),
                                downstream_relay=str(pair.get("downstream_relay", "down")),
                                upstream_trip_s=float(pair.get("upstream_trip_s", 0.0)),
                                downstream_trip_s=float(pair.get("downstream_trip_s", 0.0)),
                                min_margin_s=float(pair.get("min_margin_s", 0.2)),
                                fault_current_a=float(pair.get("fault_current_a", 0.0)),
                            )
                        except (TypeError, ValueError):
                            pass

        elif canonical in ("cable_sizing",):
            cable_loads = data.get("cable_loads_a") or data.get("cable_loads")
            cable_ampacities = data.get("cable_ampacities_a") or data.get("cable_ampacities")
            if isinstance(cable_loads, dict) and isinstance(cable_ampacities, dict):
                c_loads = {str(k): float(v) for k, v in cable_loads.items()}
                c_amp = {str(k): float(v) for k, v in cable_ampacities.items()}
                self.validate_cable_sizing(c_loads, c_amp)

        new_results = self._results[start_idx:]
        warnings = [r for r in new_results if r.severity == AssertionSeverity.WARNING]
        critical_or_fatal = [
            r for r in new_results if r.severity in (AssertionSeverity.CRITICAL, AssertionSeverity.FATAL) and not r.passed
        ]
        if self.strict_mode:
            failures = [r for r in new_results if not r.passed or r.severity == AssertionSeverity.WARNING]
        else:
            failures = critical_or_fatal

        has_critical = len(critical_or_fatal) > 0
        has_any = len(failures) > 0 or len(warnings) > 0
        passed = (not has_critical) and (not self.strict_mode or not has_any)

        summary = {
            "total_checks": len(new_results),
            "passed": sum(1 for r in new_results if r.passed and r.severity != AssertionSeverity.WARNING),
            "warnings": len(warnings),
            "failed": len(failures),
            "has_critical_failures": has_critical,
            "has_any_failures": has_any,
            "failures": [r.to_dict() for r in failures],
            "warnings_list": [r.to_dict() for r in warnings],
        }

        return AssertionReport(
            passed=passed,
            failures=failures,
            warnings=warnings,
            all_results=new_results,
            has_critical_failures=has_critical,
            has_any_failures=has_any,
            summary=summary,
        )

    def get_all_results(self) -> list[AssertionResult]:
        """Return all accumulated assertion results."""
        return list(self._results)

    def has_critical_failures(self) -> bool:
        """Check if any CRITICAL or FATAL assertions have failed."""
        return any(
            not r.passed and r.severity in (AssertionSeverity.CRITICAL, AssertionSeverity.FATAL)
            for r in self._results
        )

    def has_any_failures(self) -> bool:
        """Check if any assertions have failed (including WARNING in strict mode)."""
        if self.strict_mode:
            return any(not r.passed for r in self._results)
        return self.has_critical_failures()

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all assertion results."""
        passed = sum(1 for r in self._results if r.passed)
        failed = sum(1 for r in self._results if not r.passed)
        return {
            "total_checks": len(self._results),
            "passed": passed,
            "failed": failed,
            "has_critical_failures": self.has_critical_failures(),
            "has_any_failures": self.has_any_failures(),
            "failures": [r.to_dict() for r in self._results if not r.passed],
        }

    def clear(self) -> None:
        """Clear all accumulated results."""
        self._results.clear()


def validate_fallback_output(
    output_type: str,
    output_data: dict[str, Any],
    strict_mode: bool = True,
) -> tuple[bool, dict[str, Any]]:
    """
    Convenience function to validate AI output from a fallback model.

    This is the main entry point for the V-04 fix. It delegates to
    EngineeringAssertionLayer.validate() for standard checks.
    """
    layer = EngineeringAssertionLayer(strict_mode=strict_mode)
    report = layer.validate(output_data, output_type)

    if not report.passed:
        logger.warning(
            "V-04: Fallback output validation FAILED for %s — %d of %d checks failed. "
            "Output will be rejected or flagged.",
            output_type,
            report.summary["failed"],
            report.summary["total_checks"],
        )

    return report.passed, report.summary

