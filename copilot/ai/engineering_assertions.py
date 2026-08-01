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
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AssertionSeverity(Enum):
    """Severity level for assertion failures."""

    WARNING = "warning"  # Suspicious but not necessarily wrong
    CRITICAL = "critical"  # Physically impossible or dangerous
    FATAL = "fatal"  # Will cause injury/death if acted upon


@dataclass
class AssertionResult:
    """Result of a single engineering assertion check."""

    check_name: str
    passed: bool
    severity: AssertionSeverity = AssertionSeverity.WARNING
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

    def __init__(self, strict_mode: bool = True):
        """
        Initialize the assertion layer.

        Parameters
        ----------
        strict_mode : bool
            If True, WARNING-level failures also cause rejection.
            If False, only CRITICAL and FATAL failures cause rejection.
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

            voltage_pu = voltage_kv / nominal_voltage_kv

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

    def validate_arc_flash_results(
        self,
        incident_energy_cal_cm2: dict[str, float],
        arc_flash_boundaries_mm: Optional[dict[str, float]] = None,
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

    This is the main entry point for the V-04 fix. It should be called
    whenever an AI response is produced by a fallback model or safety-net
    prompt, before the response is shown to the user.

    Parameters
    ----------
    output_type : str
        Type of engineering output: "short_circuit", "load_flow",
        "arc_flash", "protection_coordination", "cable_sizing".
    output_data : dict
        The AI output data to validate.
    strict_mode : bool
        If True, WARNING-level failures also cause rejection.

    Returns
    -------
    tuple[bool, dict]
        (is_safe, summary) where is_safe is True if the output passes
        all critical checks, and summary contains the full assertion results.
    """
    layer = EngineeringAssertionLayer(strict_mode=strict_mode)

    if output_type == "short_circuit":
        fault_currents = output_data.get("fault_currents", {})
        if isinstance(fault_currents, dict):
            # Convert to float values
            current_ka = {}
            for k, v in fault_currents.items():
                try:
                    current_ka[k] = (
                        float(v)
                        if not isinstance(v, dict)
                        else float(v.get("magnitude", v.get("mag", 0)))
                    )
                except (TypeError, ValueError):
                    current_ka[k] = 0.0
            layer.validate_short_circuit_results(current_ka)

    elif output_type == "load_flow":
        bus_voltages = output_data.get("bus_voltages", {})
        nominal_kv = output_data.get("nominal_voltage_kv", 11.0)
        if isinstance(bus_voltages, dict):
            voltage_kv = {}
            for k, v in bus_voltages.items():
                try:
                    voltage_kv[k] = (
                        float(v)
                        if not isinstance(v, dict)
                        else float(v.get("magnitude", v.get("mag", 0)))
                    )
                except (TypeError, ValueError):
                    voltage_kv[k] = 0.0
            layer.validate_voltage_results(voltage_kv, nominal_kv)

    elif output_type == "arc_flash":
        incident_energy = output_data.get("incident_energy", {})
        boundaries = output_data.get("arc_flash_boundaries")
        if isinstance(incident_energy, dict):
            energy_cal = {}
            for k, v in incident_energy.items():
                try:
                    energy_cal[k] = float(v)
                except (TypeError, ValueError):
                    energy_cal[k] = 0.0
            boundary_mm = None
            if boundaries and isinstance(boundaries, dict):
                boundary_mm = {}
                for k, v in boundaries.items():
                    try:
                        boundary_mm[k] = float(v)
                    except (TypeError, ValueError):
                        boundary_mm[k] = 0.0
            layer.validate_arc_flash_results(energy_cal, boundary_mm)

    elif output_type == "protection_coordination":
        relay_results = output_data.get("relay_results", [])
        for relay in relay_results:
            if isinstance(relay, dict):
                layer.validate_trip_time(
                    relay_id=relay.get("relay_id", "unknown"),
                    trip_time_s=float(relay.get("trip_time_s", 0)),
                    current_a=float(relay.get("current_a", 0)),
                    pickup_a=float(relay.get("pickup_a", 0)),
                )

    elif output_type == "cable_sizing":
        cable_loads = output_data.get("cable_loads_a", {})
        cable_ampacities = output_data.get("cable_ampacities_a", {})
        if isinstance(cable_loads, dict) and isinstance(cable_ampacities, dict):
            layer.validate_cable_sizing(cable_loads, cable_ampacities)

    summary = layer.get_summary()
    is_safe = not layer.has_critical_failures() and (
        not strict_mode or not layer.has_any_failures()
    )

    if not is_safe:
        logger.warning(
            "V-04: Fallback output validation FAILED for %s — %d of %d checks failed. "
            "Output will be rejected or flagged.",
            output_type,
            summary["failed"],
            summary["total_checks"],
        )

    return is_safe, summary
