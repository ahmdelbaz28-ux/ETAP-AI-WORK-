"""
coordination/chain_coordinator.py — Automated Multi-Relay Coordination Chain Grading.

Implements automated relay grading along distribution feeders and industrial
substations according to IEEE 242 (Buff Book) and IEC 60255 standards.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from curves.curves import calculate_iec_operating_time
from relays.relay import OvercurrentRelay

logger = logging.getLogger(__name__)


@dataclass
class RelayNode:
    """Relay in a protection coordination chain."""

    relay_id: str
    name: str
    location: str
    relay: OvercurrentRelay
    ct_ratio: float = 1.0  # Primary / Secondary CT ratio (e.g., 200/5 = 40.0)
    load_current_a: float = 50.0  # Full load current in primary Amperes
    max_fault_current_a: float = 5000.0  # Max bolted 3-phase fault at this bus
    min_fault_current_a: float = 1500.0  # Min fault current (remote or phase-to-ground)


@dataclass
class ChainGradingResult:
    """Results from protection chain grading."""

    success: bool
    cti_target_s: float
    relays: List[RelayNode]
    pair_evaluations: List[Dict[str, Any]] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)
    total_clearance_time_s: float = 0.0


class ChainCoordinator:
    """
    Automated Multi-Relay Coordination Engine.
    Grades overcurrent relays along a radial feeder from downstream load to upstream source.
    """

    def __init__(self, default_cti_s: float = 0.30, min_cti_s: float = 0.20):
        """
        Parameters
        ----------
        default_cti_s : float
            Target Coordination Time Interval (CTI). Typical range 0.25 - 0.40 s per IEEE 242.
        min_cti_s : float
            Absolute minimum allowable CTI before raising a selectivity violation.
        """
        self.default_cti_s = default_cti_s
        self.min_cti_s = min_cti_s

    def grade_chain(
        self,
        chain: List[RelayNode],
        cti_target_s: Optional[float] = None,
        min_tms: float = 0.05,
        max_tms: float = 3.0,
        tms_step: float = 0.01,
        security_factor: float = 1.25,
    ) -> ChainGradingResult:
        """
        Automatically grade a chain of relays from downstream to upstream.

        Parameters
        ----------
        chain : List[RelayNode]
            List of relays ordered from UPSTREAM (index 0, closest to source)
            to DOWNSTREAM (last index, closest to load).
        cti_target_s : float, optional
            Target coordination time interval (default: self.default_cti_s).
        min_tms, max_tms : float
            TMS bounds for numerical relays.
        tms_step : float
            Discrete setting step size for relay dials.
        security_factor : float
            Multiplier above load current for pickup setting (default: 1.25).

        Returns
        -------
        ChainGradingResult
            Graded relay chain with updated TMS settings and margin verifications.
        """
        if len(chain) < 1:
            return ChainGradingResult(success=True, cti_target_s=0.3, relays=[])

        cti_target = cti_target_s or self.default_cti_s
        violations = []

        # 1. Grade the furthest downstream relay (chain[-1])
        downstream_relay = chain[-1]
        # Set pickup above load current in secondary per-unit
        ip_primary = downstream_relay.load_current_a * security_factor
        ip_relay = ip_primary / max(downstream_relay.ct_ratio, 1.0)
        downstream_relay.relay.Ip = float(ip_relay)
        downstream_relay.relay.TMS = float(min_tms)

        # 2. Backwards iterative grading: from chain[-2] up to chain[0]
        for k in range(len(chain) - 2, -1, -1):
            up = chain[k]
            down = chain[k + 1]

            # Set pickup for upstream relay
            up_ip_primary = max(up.load_current_a * security_factor, down.load_current_a * security_factor * 1.05)
            up_ip_relay = up_ip_primary / max(up.ct_ratio, 1.0)
            up.relay.Ip = float(up_ip_relay)

            # Evaluate downstream relay operating time at downstream max fault
            # Fault current seen by downstream relay (relay secondary or primary per-unit)
            if_down_a = down.max_fault_current_a
            if_down_relay = if_down_a / max(down.ct_ratio, 1.0)

            t_down_res = calculate_iec_operating_time(
                i_fault=if_down_relay,
                i_setting=down.relay.Ip,
                tms=down.relay.TMS,
                curve_type=down.relay.curve_type,
            )
            t_down = t_down_res["operating_time_s"]

            # Required operating time for upstream relay to maintain CTI
            t_up_required = t_down + cti_target

            # Upstream fault current at the downstream bus fault
            if_up_a = down.max_fault_current_a
            if_up_relay = if_up_a / max(up.ct_ratio, 1.0)

            # Find smallest TMS for upstream relay that yields t_up >= t_up_required
            best_tms = max_tms
            found_tms = False

            # Numerical sweep over discrete TMS increments
            test_tms_values = np.arange(min_tms, max_tms + tms_step, tms_step)
            for trial_tms in test_tms_values:
                trial_res = calculate_iec_operating_time(
                    i_fault=if_up_relay,
                    i_setting=up.relay.Ip,
                    tms=float(trial_tms),
                    curve_type=up.relay.curve_type,
                )
                if trial_res["operating_time_s"] >= t_up_required - 1e-4:
                    best_tms = round(float(trial_tms), 3)
                    found_tms = True
                    break

            if not found_tms:
                best_tms = max_tms
                violations.append(
                    f"Relay {up.relay_id} could not achieve target CTI {cti_target:.2f} s with downstream {down.relay_id} (hit max TMS {max_tms})"
                )

            up.relay.TMS = best_tms

        # 3. Verification across the entire chain
        eval_result = self.verify_coordination(chain, cti_min_s=self.min_cti_s)
        eval_result.cti_target_s = cti_target
        if violations:
            eval_result.violations.extend(violations)
            eval_result.success = False

        return eval_result

    def verify_coordination(self, chain: List[RelayNode], cti_min_s: Optional[float] = None) -> ChainGradingResult:
        """
        Verify selectivity and margins between all adjacent relay pairs in the chain.
        """
        min_cti = cti_min_s or self.min_cti_s
        pair_evaluations: List[Dict[str, Any]] = []
        violations: List[str] = []
        is_success = True

        for i in range(len(chain) - 1):
            up = chain[i]
            down = chain[i + 1]

            # Evaluate at downstream max fault
            if_max_down = down.max_fault_current_a
            if_up_max = if_max_down / max(up.ct_ratio, 1.0)
            if_down_max = if_max_down / max(down.ct_ratio, 1.0)

            t_up_max = calculate_iec_operating_time(
                i_fault=if_up_max,
                i_setting=up.relay.Ip,
                tms=up.relay.TMS,
                curve_type=up.relay.curve_type,
            )["operating_time_s"]

            t_down_max = calculate_iec_operating_time(
                i_fault=if_down_max,
                i_setting=down.relay.Ip,
                tms=down.relay.TMS,
                curve_type=down.relay.curve_type,
            )["operating_time_s"]

            margin_max = t_up_max - t_down_max

            # Evaluate at downstream min fault
            if_min_down = down.min_fault_current_a
            if_up_min = if_min_down / max(up.ct_ratio, 1.0)
            if_down_min = if_min_down / max(down.ct_ratio, 1.0)

            t_up_min = calculate_iec_operating_time(
                i_fault=if_up_min,
                i_setting=up.relay.Ip,
                tms=up.relay.TMS,
                curve_type=up.relay.curve_type,
            )["operating_time_s"]

            t_down_min = calculate_iec_operating_time(
                i_fault=if_down_min,
                i_setting=down.relay.Ip,
                tms=down.relay.TMS,
                curve_type=down.relay.curve_type,
            )["operating_time_s"]

            margin_min = t_up_min - t_down_min

            pair_coordinated = (margin_max >= min_cti) and (margin_min >= min_cti)
            if not pair_coordinated:
                is_success = False
                violations.append(
                    f"Margin violation between {up.relay_id} and {down.relay_id}: "
                    f"CTI at max fault = {margin_max:.3f} s, CTI at min fault = {margin_min:.3f} s (required >= {min_cti:.2f} s)"
                )

            pair_evaluations.append({
                "upstream_id": up.relay_id,
                "downstream_id": down.relay_id,
                "margin_at_max_fault_s": float(margin_max),
                "margin_at_min_fault_s": float(margin_min),
                "t_upstream_s": float(t_up_max),
                "t_downstream_s": float(t_down_max),
                "is_coordinated": bool(pair_coordinated),
            })

        # Total clearance time at upstream source for worst-case downstream fault
        worst_t = pair_evaluations[0]["t_upstream_s"] if pair_evaluations else 0.0

        return ChainGradingResult(
            success=is_success,
            cti_target_s=self.default_cti_s,
            relays=chain,
            pair_evaluations=pair_evaluations,
            violations=violations,
            total_clearance_time_s=worst_t,
        )

    def generate_report(self, result: ChainGradingResult) -> str:
        """Generate human-readable engineering coordination report."""
        lines = []
        lines.append("=" * 80)
        lines.append("        AHMEDETAP - AUTOMATED PROTECTION COORDINATION CHAIN REPORT")
        lines.append("        Standards Compliance: IEEE 242 (Buff Book) / IEC 60255")
        lines.append("=" * 80)
        lines.append(f"Coordination Status: {'✓ FULLY COORDINATED' if result.success else '⚠ MARGIN VIOLATIONS DETECTED'}")
        lines.append(f"Target CTI Margin  : {result.cti_target_s:.2f} s")
        lines.append(f"Max Clearing Time  : {result.total_clearance_time_s:.3f} s")
        lines.append("")
        lines.append("RELAY SETTINGS SUMMARY")
        lines.append("-" * 80)
        lines.append(f"{'Relay ID':<10} {'Name':<18} {'Location':<18} {'Curve Type':<18} {'CT Ratio':<9} {'Ip (A)':<8} {'TMS':<7}")
        lines.append("-" * 80)

        for r in result.relays:
            ip_primary = r.relay.Ip * r.ct_ratio
            lines.append(
                f"{r.relay_id:<10} {r.name:<18} {r.location:<18} {r.relay.curve_type:<18} {r.ct_ratio:<9.1f} {ip_primary:<8.1f} {r.relay.TMS:<7.3f}"
            )

        lines.append("")
        lines.append("ADJACENT PAIR COORDINATION MARGINS")
        lines.append("-" * 80)
        lines.append(f"{'Upstream':<12} {'Downstream':<12} {'T_up (s)':<12} {'T_down (s)':<12} {'Margin (s)':<12} {'Status':<10}")
        lines.append("-" * 80)

        for p in result.pair_evaluations:
            status = "COORDINATED" if p["is_coordinated"] else "FAIL"
            lines.append(
                f"{p['upstream_id']:<12} {p['downstream_id']:<12} {p['t_upstream_s']:<12.3f} {p['t_downstream_s']:<12.3f} {p['margin_at_max_fault_s']:<12.3f} {status:<10}"
            )

        if result.violations:
            lines.append("")
            lines.append("⚠ COORDINATION VIOLATIONS")
            lines.append("-" * 80)
            for v in result.violations:
                lines.append(f"  • {v}")

        lines.append("=" * 80)
        return "\n".join(lines)
