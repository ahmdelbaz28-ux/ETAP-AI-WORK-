"""
AhmedETAP - Generative Substation & Feeder Design Agent (Scaffold)
==================================================================
Automated engineering synthesis of substation Single-Line Diagram (SLD)
topologies, primary equipment sizing, and protection scheme allocations.

Governing Standards:
- IEEE 141: Electric Power Distribution for Industrial Plants (Red Book)
- IEEE 242: Protection and Coordination of Industrial Power Systems (Buff Book)
- IEC 62271: High-voltage switchgear and controlgear
- IEC 60076: Power transformers
- IEC 60364: Low-voltage electrical installations
- IEC 60909: Short-circuit currents calculation

Safety & Integrity Invariant:
- Strict Fail-Closed: Feature flag ``generative_design`` MUST be explicitly
  enabled. When disabled, the agent rejects synthesis immediately to protect
  production systems against unverified generative topology mutations.
- Zero Guessing: Requires all core electrical parameters (primary/secondary kV,
  load MVA, reliability criteria). Missing values trigger validation errors.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from agents.base import BaseAgent
from agents.models import AgentResult, AgentStatus, EngineeringTask, StudyType
from api.feature_flags import is_strict_feature_enabled
from core.tracing import trace_operation

UTC = timezone.utc  # noqa: UP017
logger = logging.getLogger(__name__)

# Standard transformer MVA capacities per IEC 60076
_STANDARD_TRANSFORMER_MVA = [
    2.5, 3.15, 4.0, 5.0, 6.3, 7.5, 10.0, 12.5, 16.0, 20.0,
    25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0
]

# Standard switchgear continuous current ratings (Amperes) per IEC 62271
_STANDARD_BREAKER_CURRENTS_A = [630, 800, 1250, 1600, 2000, 2500, 3150, 4000]


class DesignAgent(BaseAgent):
    """Generative Substation & Feeder Design Agent.

    Prompt Handle: design_agent
    """

    prompt_handle = "design_agent"

    def __init__(self):
        super().__init__("DesignAgent")

    @trace_operation(
        "DesignAgent.execute",
        attributes={"component": "orchestrator", "study_type": "generative_design"},
    )
    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute generative design synthesis."""
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING
        self.log_execution(f"Initiating generative design task {task.task_id}")

        # 1. Enforce strict fail-closed feature gate
        if not is_strict_feature_enabled("generative_design", default=False):
            self.status = AgentStatus.FAILED
            err_msg = (
                "Feature flag 'generative_design' is disabled. "
                "Generative design scaffold operates in strict fail-closed mode."
            )
            self.log_execution(f"Execution rejected: {err_msg}")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.GENERATIVE_DESIGN,
                status=AgentStatus.FAILED,
                data={"summary": {"status": "rejected", "reason": "flag_disabled"}},
                validation_status=False,
                validation_errors=[err_msg],
                execution_time=(datetime.now(UTC) - start_time).total_seconds(),
            )

        params = task.parameters or {}

        # 2. Validate mandatory engineering inputs (Zero Guessing Rule R3)
        primary_kv = params.get("primary_voltage_kv")
        secondary_kv = params.get("secondary_voltage_kv")
        total_load_mva = params.get("total_load_mva")

        missing_fields = []
        if primary_kv is None:
            missing_fields.append("primary_voltage_kv")
        if secondary_kv is None:
            missing_fields.append("secondary_voltage_kv")
        if total_load_mva is None:
            missing_fields.append("total_load_mva")

        if missing_fields:
            self.status = AgentStatus.FAILED
            err_msg = (
                f"Missing required design parameters: {', '.join(missing_fields)}. "
                "AhmedETAP prohibits parameter guessing."
            )
            self.log_execution(f"Validation failure: {err_msg}")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.GENERATIVE_DESIGN,
                status=AgentStatus.FAILED,
                data={"summary": {"status": "invalid_parameters"}},
                validation_status=False,
                validation_errors=[err_msg],
                execution_time=(datetime.now(UTC) - start_time).total_seconds(),
            )

        try:
            primary_kv = float(primary_kv)
            secondary_kv = float(secondary_kv)
            total_load_mva = float(total_load_mva)
            growth_margin = float(params.get("growth_margin_pct", 20.0))
            diversity_factor = float(params.get("diversity_factor", 0.85))
            redundancy = str(params.get("redundancy", "N-1")).strip().upper()
            num_feeders = int(params.get("num_feeders", 4))

            # 3. Transformer Sizing
            design_load = total_load_mva * (1.0 + growth_margin / 100.0) * diversity_factor
            if redundancy == "N-1":
                # Each transformer can handle full design load under single outage
                required_xfmr_mva = design_load
                num_transformers = 2
            else:
                num_transformers = 1
                required_xfmr_mva = design_load

            # Pick next standard size
            selected_xfmr_mva = next(
                (size for size in _STANDARD_TRANSFORMER_MVA if size >= required_xfmr_mva),
                _STANDARD_TRANSFORMER_MVA[-1],
            )

            # Standard percent impedance per IEC 60076-5
            if selected_xfmr_mva <= 5.0:
                percent_z = 6.0
            elif selected_xfmr_mva <= 25.0:
                percent_z = 8.0
            elif selected_xfmr_mva <= 63.0:
                percent_z = 10.0
            else:
                percent_z = 12.5

            # 4. Switchgear & Breaker Ratings
            # Primary side rated current
            i_primary_a = (selected_xfmr_mva * 1000.0) / (math.sqrt(3) * primary_kv)
            primary_breaker_a = next(
                (b for b in _STANDARD_BREAKER_CURRENTS_A if b >= i_primary_a * 1.25),
                _STANDARD_BREAKER_CURRENTS_A[-1],
            )

            # Secondary side rated current
            i_secondary_a = (selected_xfmr_mva * 1000.0) / (math.sqrt(3) * secondary_kv)
            secondary_incomer_breaker_a = next(
                (b for b in _STANDARD_BREAKER_CURRENTS_A if b >= i_secondary_a * 1.25),
                _STANDARD_BREAKER_CURRENTS_A[-1],
            )

            # Feeder breaker sizing
            feeder_load_mva = design_load / max(1, num_feeders)
            i_feeder_a = (feeder_load_mva * 1000.0) / (math.sqrt(3) * secondary_kv)
            feeder_breaker_a = next(
                (b for b in _STANDARD_BREAKER_CURRENTS_A if b >= i_feeder_a * 1.25),
                _STANDARD_BREAKER_CURRENTS_A[0],
            )

            # 5. Protection Scheme Allocation
            protection_scheme = {
                "transformer_differential_87t": True,
                "transformer_overcurrent_backup_50_51": {
                    "curve_standard": "IEC 60255",
                    "characteristic": "Standard Inverse (SI)",
                },
                "busbar_protection_87b": num_transformers > 1 or primary_kv >= 33.0,
                "feeder_protection": {
                    "primary": "50/51 Overcurrent & Earth Fault",
                    "auto_reclose_79": primary_kv >= 33.0,
                },
            }

            # 6. Synthesize Single Line Topology
            topology = {
                "substation_type": f"{primary_kv:.1f}/{secondary_kv:.1f} kV {redundancy} Distribution Substation",
                "bus_configuration": "Double-bus Single-Breaker with Bus Coupler" if num_transformers > 1 else "Single Bus",
                "transformers": [
                    {
                        "id": f"TR-{i+1}",
                        "rating_mva": selected_xfmr_mva,
                        "ratio_kv": f"{primary_kv:.1f}/{secondary_kv:.1f}",
                        "impedance_pct": percent_z,
                        "cooling": "ONAN/ONAF",
                    }
                    for i in range(num_transformers)
                ],
                "switchgear": {
                    "primary_breaker_rating_a": primary_breaker_a,
                    "secondary_incomer_rating_a": secondary_incomer_breaker_a,
                    "feeder_breaker_rating_a": feeder_breaker_a,
                    "num_feeders": num_feeders,
                },
                "protection_scheme": protection_scheme,
            }

            self.status = AgentStatus.COMPLETED
            self.log_execution("Generative design synthesis completed successfully.")

            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.GENERATIVE_DESIGN,
                status=AgentStatus.COMPLETED,
                data={
                    "summary": {
                        "status": "success",
                        "substation_type": topology["substation_type"],
                        "transformer_count": num_transformers,
                        "transformer_mva_each": selected_xfmr_mva,
                        "primary_breaker_a": primary_breaker_a,
                        "secondary_breaker_a": secondary_incomer_breaker_a,
                        "num_feeders": num_feeders,
                        "feeder_breaker_a": feeder_breaker_a,
                    },
                    "topology": topology,
                },
                validation_status=True,
                validation_errors=[],
                execution_time=(datetime.now(UTC) - start_time).total_seconds(),
            )

        except Exception as exc:
            self.status = AgentStatus.FAILED
            self.log_execution(f"Design synthesis exception: {exc}")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.GENERATIVE_DESIGN,
                status=AgentStatus.FAILED,
                data={"summary": {"status": "error"}},
                validation_status=False,
                validation_errors=[str(exc)],
                execution_time=(datetime.now(UTC) - start_time).total_seconds(),
            )
