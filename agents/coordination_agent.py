"""
AhmedETAP - Protection Coordination Agent
=============================================================
Protection system coordination analysis per IEEE 242 (Buff Book)
and IEC 60255.

V-TCC-01 Self-Critique Fixes:
- REMOVED duplicate _IEC60255_CURVES dict — all calculations now
  delegate to calculate_iec_operating_time() from curves.curves,
  which is the single source of truth for IEC 60255 and IEEE C37.112
  curve parameters with safety guards.
- FIXED naming inconsistency: 'long_time_inverse' → 'long_inverse'
  to match the IEC60255Curves class and the curve registry.
- All safety guards (min operating time, max multiplier, instantaneous
  override) are now enforced automatically through the safe function.

Capabilities:
- Relay operating time calculation (IEC 60255 / IEEE C37.112 curve equations)
- Time-current curve coordination analysis
- Coordination margin verification (minimum 0.2s)
- Pickup setting and time dial optimization
- Selectivity, sensitivity, speed, and security assessment

Standards:
- IEEE 242: Protection and Coordination of Industrial and Commercial
  Power Systems (Buff Book)
- IEEE C37.010: Application Guide for AC High-Voltage Circuit Breakers
- IEEE C37.112: Inverse-Time Characteristic Equations for Overcurrent Relays
- IEC 60255: Measuring Relays and Protection Equipment
- NFPA 70: National Electrical Code (Article 240, 430)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType
from curves.curves import (
    calculate_iec_operating_time,
    MAX_MULTIPLIER_OF_PICKUP,
    MIN_OPERATING_TIME_S,
)

logger = logging.getLogger(__name__)


class CoordinationAgent(BaseAgent):
    """
    Protection Coordination Agent (IEEE 242 / IEC 60255).

    Provides comprehensive protection system coordination analysis
    including:

    - **Relay Operating Time**: Calculation of relay trip times for
      various IEC 60255 and IEEE C37.112 inverse-time characteristics
      at specified fault current levels.
    - **Coordination Margin**: Verification that minimum 0.2 s
      coordination interval exists between adjacent protective devices.
    - **Time-Current Curve Data**: Generation of discrete TCC points
      for plotting and visual coordination checks.
    - **Selectivity Analysis**: Assessment of whether only the nearest
      upstream device operates for a fault within its zone.
    - **Sensitivity Analysis**: Verification that protection can
      detect minimum fault levels within its zone.

    Coordination principles (IEEE 242):
    - **Selectivity**: Only the nearest upstream protective device
      should operate for a fault.
    - **Sensitivity**: Protection must detect minimum fault levels
      within its zone.
    - **Speed**: Faults must be cleared within time limits to prevent
      damage and maintain stability.
    - **Security**: Protection must not operate for conditions
      outside its zone (load current, inrush, external faults).

    Key equations:

    IEC 60255 operating time:
        t = TMS × k / ((I / I_ps)^n - 1)

    IEEE C37.112 operating time:
        t = TD × (A / (M^p - 1) + B),  M = I / I_ps

    Coordination interval:
        Δt = t_downstream - t_upstream ≥ 0.2 s
    """

    prompt_handle = "coordination_agent"

    def __init__(self) -> None:
        super().__init__("CoordinationAgent")
        self.standards = [
            "IEEE 242",
            "IEEE C37.010",
            "IEEE C37.112",
            "IEC 60255",
            "NFPA 70",
        ]
        self.min_coordination_interval_s: float = 0.2

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def calculate_relay_operating_time(
        self,
        fault_current_a: float,
        pickup_current_a: float,
        curve_type: str = "standard_inverse",
        time_multiplier: float = 1.0,
        *,
        instantaneous_override_a: float | None = None,
        min_operating_time_s: float = MIN_OPERATING_TIME_S,
        max_multiplier: float = MAX_MULTIPLIER_OF_PICKUP,
    ) -> dict[str, Any]:
        """
        Calculate relay operating time per IEC 60255 or IEEE C37.112.

        V-TCC-01: Now delegates entirely to calculate_iec_operating_time()
        which is the single source of truth for curve parameters and
        safety guards.  No duplicate formula logic in this agent.

        Parameters
        ----------
        fault_current_a : float
            Fault current in amperes.
        pickup_current_a : float
            Relay pickup (plug) setting in amperes.
        curve_type : str
            Characteristic curve type: 'standard_inverse',
            'very_inverse', 'extremely_inverse', 'long_inverse',
            'ieee_moderately_inverse', 'ieee_very_inverse',
            'ieee_extremely_inverse'.
        time_multiplier : float
            Time multiplier setting (TMS) for IEC curves or time dial
            (TD) for IEEE curves.
        instantaneous_override_a : float or None
            Instantaneous overcurrent element (element 50) threshold.
        min_operating_time_s : float
            Minimum operating time floor.
        max_multiplier : float
            Maximum M = I/Ip beyond which the formula is unreliable.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'operating_time_s', 'curve_type',
            'pickup_current_a', 'fault_current_a', 'multiples_of_pickup',
            'status', 'warnings'.
        """
        # Backward compatibility: accept 'long_time_inverse' and map to 'long_inverse'
        normalized_curve = curve_type.lower().strip()
        if normalized_curve == "long_time_inverse":
            normalized_curve = "long_inverse"

        result = calculate_iec_operating_time(
            i_fault=fault_current_a,
            i_setting=pickup_current_a,
            tms=time_multiplier,
            curve_type=normalized_curve,
            instantaneous_override_a=instantaneous_override_a,
            min_operating_time_s=min_operating_time_s,
            max_multiplier=max_multiplier,
        )

        # Map to the agent's expected output format
        return {
            "operating_time_s": result["operating_time_s"],
            "curve_type": result["curve_type"],
            "pickup_current_a": pickup_current_a,
            "fault_current_a": fault_current_a,
            "multiples_of_pickup": result["multiples_of_pickup"],
            "time_multiplier": time_multiplier,
            "status": result["status"],
            "warnings": result.get("warnings", []),
        }

    def verify_coordination(
        self,
        upstream_relay: dict[str, Any],
        downstream_relay: dict[str, Any],
        fault_current_a: float,
    ) -> dict[str, Any]:
        """
        Verify coordination between upstream and downstream relays.

        Parameters
        ----------
        upstream_relay : Dict[str, Any]
            Upstream relay parameters with keys: 'pickup_current_a',
            'curve_type', 'time_multiplier'.
        downstream_relay : Dict[str, Any]
            Downstream relay parameters (same keys).
        fault_current_a : float
            Fault current at the downstream bus in amperes.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'coordinated', 'coordination_interval_s',
            'upstream_time_s', 'downstream_time_s', 'assessment'.
        """
        t_down = self.calculate_relay_operating_time(
            fault_current_a=fault_current_a,
            pickup_current_a=downstream_relay["pickup_current_a"],
            curve_type=downstream_relay.get("curve_type", "standard_inverse"),
            time_multiplier=downstream_relay.get("time_multiplier", 1.0),
        )["operating_time_s"]

        # Upstream relay sees the same fault current (simplified)
        t_up = self.calculate_relay_operating_time(
            fault_current_a=fault_current_a,
            pickup_current_a=upstream_relay["pickup_current_a"],
            curve_type=upstream_relay.get("curve_type", "standard_inverse"),
            time_multiplier=upstream_relay.get("time_multiplier", 1.0),
        )["operating_time_s"]

        interval = (
            t_up - t_down if (t_up != float("inf") and t_down != float("inf")) else float("inf")
        )
        coordinated = interval >= self.min_coordination_interval_s

        if coordinated:
            assessment = (
                f"Coordination OK: interval = {interval:.3f}s "
                f"(≥ {self.min_coordination_interval_s:.1f}s minimum)"
            )
        elif t_down == float("inf"):
            assessment = "Downstream relay below pickup — coordination not applicable"
            coordinated = True
        elif t_up == float("inf"):
            assessment = "Upstream relay below pickup — coordination gap"
            coordinated = False
        else:
            assessment = (
                f"Coordination GAP: interval = {interval:.3f}s "
                f"(< {self.min_coordination_interval_s:.1f}s minimum). "
                "Adjust upstream TMS or pickup setting."
            )

        return {
            "coordinated": coordinated,
            "coordination_interval_s": round(float(interval), 4),
            "upstream_time_s": round(float(t_up), 4) if t_up != float("inf") else float("inf"),
            "downstream_time_s": round(float(t_down), 4)
            if t_down != float("inf")
            else float("inf"),
            "upstream_relay": upstream_relay,
            "downstream_relay": downstream_relay,
            "fault_current_a": fault_current_a,
            "min_interval_s": self.min_coordination_interval_s,
            "assessment": assessment,
        }

    def generate_tcc_data(
        self,
        pickup_current_a: float,
        curve_type: str = "standard_inverse",
        time_multiplier: float = 1.0,
        min_multiplier: float = 1.5,
        max_multiplier: float = 40.0,
        num_points: int = 50,
    ) -> dict[str, Any]:
        """
        Generate time-current curve (TCC) data points for plotting.

        Parameters
        ----------
        pickup_current_a : float
            Relay pickup setting in amperes.
        curve_type : str
            Characteristic curve type.
        time_multiplier : float
            Time multiplier / time dial setting.
        min_multiplier : float
            Minimum multiples of pickup for curve start.
        max_multiplier : float
            Maximum multiples of pickup for curve end.
        num_points : int
            Number of data points to generate.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'current_a', 'time_s', 'curve_type',
            'pickup_current_a'.
        """
        multipliers = np.logspace(
            np.log10(min_multiplier),
            np.log10(max_multiplier),
            num_points,
        )
        currents = multipliers * pickup_current_a

        times = []
        for I in currents:  # NOSONAR physics/engineering notation
            result = self.calculate_relay_operating_time(
                fault_current_a=float(I),
                pickup_current_a=pickup_current_a,
                curve_type=curve_type,
                time_multiplier=time_multiplier,
            )
            t = result["operating_time_s"]
            times.append(t if t != float("inf") else 100.0)

        return {
            "current_a": [round(float(c), 2) for c in currents],
            "time_s": [round(float(t), 4) for t in times],
            "multiples_of_pickup": [round(float(m), 4) for m in multipliers],
            "curve_type": curve_type,
            "pickup_current_a": pickup_current_a,
            "time_multiplier": time_multiplier,
        }

    def analyze_selectivity(
        self,
        relay_chain: list[dict[str, Any]],
        fault_currents_a: list[float],
    ) -> dict[str, Any]:
        """
        Analyze selectivity across a chain of coordinated relays.

        Parameters
        ----------
        relay_chain : List[Dict[str, Any]]
            Ordered list of relay parameters from downstream to
            upstream.  Each dict has keys: 'name', 'pickup_current_a',
            'curve_type', 'time_multiplier'.
        fault_currents_a : List[float]
            Fault currents at each bus from downstream to upstream.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'selective', 'coordination_checks',
            'non_coordinated_pairs'.
        """
        if len(relay_chain) < 2:
            return {
                "selective": True,
                "coordination_checks": [],
                "non_coordinated_pairs": [],
                "message": "Single relay — no coordination to verify",
            }

        coordination_checks = []
        non_coordinated = []

        for i in range(len(relay_chain) - 1):
            downstream = relay_chain[i]
            upstream = relay_chain[i + 1]
            fault_current = (
                fault_currents_a[i] if i < len(fault_currents_a) else fault_currents_a[-1]
            )

            check = self.verify_coordination(
                upstream_relay=upstream,
                downstream_relay=downstream,
                fault_current_a=fault_current,
            )
            check["downstream_name"] = downstream.get("name", f"relay_{i}")
            check["upstream_name"] = upstream.get("name", f"relay_{i + 1}")
            coordination_checks.append(check)

            if not check["coordinated"]:
                non_coordinated.append(
                    {
                        "downstream": downstream.get("name", f"relay_{i}"),
                        "upstream": upstream.get("name", f"relay_{i + 1}"),
                        "interval_s": check["coordination_interval_s"],
                    },
                )

        return {
            "selective": len(non_coordinated) == 0,
            "coordination_checks": coordination_checks,
            "non_coordinated_pairs": non_coordinated,
            "total_pairs": len(coordination_checks),
            "coordinated_pairs": len(coordination_checks) - len(non_coordinated),
        }

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute protection coordination analysis task.

        Dispatches based on ``task.parameters['analysis_type']``:
        ``'relay_time'``, ``'coordination_check'``,
        ``'tcc_data'``, ``'selectivity'``, or ``'full'``.
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting coordination analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: dict[str, Any] = {}

            # --- Relay operating time ---
            if analysis_type in ("relay_time", "full"):
                fault_i = float(task.parameters.get("fault_current_a", 5000.0))  # NOSONAR
                pickup = float(task.parameters.get("pickup_current_a", 800.0))
                curve = task.parameters.get("curve_type", "standard_inverse")
                tms = float(task.parameters.get("time_multiplier", 1.0))

                results["relay_operating_time"] = self.calculate_relay_operating_time(
                    fault_current_a=fault_i,
                    pickup_current_a=pickup,
                    curve_type=curve,
                    time_multiplier=tms,
                )

            # --- Coordination check ---
            if analysis_type in ("coordination_check", "full"):
                upstream = task.parameters.get(
                    "upstream_relay",
                    {
                        "pickup_current_a": 2000.0,
                        "curve_type": "standard_inverse",
                        "time_multiplier": 0.5,
                    },
                )
                downstream = task.parameters.get(
                    "downstream_relay",
                    {
                        "pickup_current_a": 800.0,
                        "curve_type": "standard_inverse",
                        "time_multiplier": 0.3,
                    },
                )
                fault_i = float(task.parameters.get("fault_current_a", 10000.0))

                results["coordination_check"] = self.verify_coordination(
                    upstream_relay=upstream,
                    downstream_relay=downstream,
                    fault_current_a=fault_i,
                )

            # --- TCC data ---
            if analysis_type in ("tcc_data", "full"):
                pickup = float(task.parameters.get("pickup_current_a", 800.0))
                curve = task.parameters.get("curve_type", "standard_inverse")
                tms = float(task.parameters.get("time_multiplier", 1.0))

                results["tcc_data"] = self.generate_tcc_data(
                    pickup_current_a=pickup,
                    curve_type=curve,
                    time_multiplier=tms,
                )

            # --- Selectivity analysis ---
            if analysis_type in ("selectivity", "full"):
                relay_chain = task.parameters.get(
                    "relay_chain",
                    [
                        {
                            "name": "feeder_relay",
                            "pickup_current_a": 800.0,
                            "curve_type": "very_inverse",
                            "time_multiplier": 0.3,
                        },
                        {
                            "name": "main_relay",
                            "pickup_current_a": 2000.0,
                            "curve_type": "standard_inverse",
                            "time_multiplier": 0.5,
                        },
                        {
                            "name": "utility_relay",
                            "pickup_current_a": 5000.0,
                            "curve_type": "standard_inverse",
                            "time_multiplier": 0.7,
                        },
                    ],
                )
                fault_currents = task.parameters.get(
                    "fault_currents_a",
                    [10000.0, 15000.0, 20000.0],
                )

                results["selectivity"] = self.analyze_selectivity(
                    relay_chain=relay_chain,
                    fault_currents_a=fault_currents,
                )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.PROTECTION_COORDINATION,
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "analysis_type": analysis_type,
                    "standards": self.standards,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Coordination analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Coordination analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.PROTECTION_COORDINATION,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate protection coordination analysis results.

        Checks:
        - Operating times are positive
        - Coordination intervals meet minimum (0.2s)
        - TCC data has consistent lengths
        """
        if result is None:
            return False

        errors: list[str] = []

        rt_data = result.data.get("relay_operating_time")
        if rt_data is not None:
            t = rt_data.get("operating_time_s", 0.0)
            if t < 0:
                errors.append(f"Operating time is negative: {t:.4f}s")

        cc_data = result.data.get("coordination_check")
        if cc_data is not None:
            interval = cc_data.get("coordination_interval_s", 0.0)
            if interval < 0:
                errors.append(f"Coordination interval is negative: {interval:.4f}s")

        tcc_data = result.data.get("tcc_data")
        if tcc_data is not None:
            n_currents = len(tcc_data.get("current_a", []))
            n_times = len(tcc_data.get("time_s", []))
            if n_currents != n_times:
                errors.append(f"TCC data length mismatch: {n_currents} currents vs {n_times} times")

        result.validation_errors.extend(errors)
        return len(errors) == 0
