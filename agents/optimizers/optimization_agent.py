"""
agents/optimizers/optimization_agent.py — Optimization Specialist Agent for AhmedETAP.

Integrates Particle Swarm Optimization (PSO), multi-objective Pareto exploration,
optimal reactive power and DER placement, and harmonic filter design into the
AhmedETAP multi-agent ecosystem.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask
from coordination.optimizers.pso_coordinator import PSOCoordinationEngine
from engine.optimizers.filter_design_pso import HarmonicFilterOptimizer
from engine.optimizers.multi_objective import MultiObjectivePSO
from engine.optimizers.placement_pso import OptimalPlacementPSO
from load_flow.optimizers.pso_opf import PSOOptimalPowerFlow

logger = logging.getLogger(__name__)


class OptimizationAgent(BaseAgent):
    """Specialist agent delivering swarm and metaheuristic optimizations."""

    prompt_handle: str = "fallback_agent"

    def __init__(self) -> None:
        super().__init__("OptimizationAgent")
        self.standards = ["IEEE 1547", "IEEE 519", "IEC 60255", "IEEE 3002.7"]

    @property
    def name(self) -> str:
        return self.agent_name

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """Execute an optimization study requested by the orchestrator."""
        study_type = task.parameters.get("optimization_type", "placement")
        logger.info("OptimizationAgent executing study: %s", study_type)

        try:
            if study_type in ("capacitor_placement", "placement"):
                res = self._run_placement(task.parameters)
            elif study_type in ("harmonic_filter", "filter_design"):
                res = self._run_filter_design(task.parameters)
            elif study_type in ("protection_coordination", "pso_coordination"):
                res = self._run_coordination(task.parameters)
            elif study_type in ("ac_opf", "pso_opf"):
                res = self._run_opf(task.parameters)
            else:
                return AgentResult(
                    task_id=task.id,
                    agent_name=self.name,
                    status=AgentStatus.FAILED,
                    error=f"Unsupported optimization type: {study_type}",
                )

            return AgentResult(
                task_id=task.id,
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                data=res,
            )
        except Exception as exc:
            logger.exception("OptimizationAgent failed: %s", exc)
            return AgentResult(
                task_id=task.id,
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error=str(exc),
            )

    def _run_placement(self, params: Dict[str, Any]) -> Dict[str, Any]:
        ybus = params.get("ybus")
        bus_ids = params.get("bus_ids", [])
        load_data = params.get("load_data", {})
        cand_buses = params.get("candidate_buses")
        max_q = float(params.get("max_total_q_mvar", 15.0))

        opt = OptimalPlacementPSO(
            ybus=ybus,
            bus_ids=bus_ids,
            load_data=load_data,
            candidate_buses=cand_buses,
            max_total_q_mvar=max_q,
        )
        res = opt.optimize_capacitor_placement()
        return {
            "optimal_allocations_mvar": res.optimal_allocations,
            "initial_losses_mw": res.initial_losses_mw,
            "optimized_losses_mw": res.optimized_losses_mw,
            "loss_reduction_pct": res.loss_reduction_pct,
            "min_voltage_before": res.min_voltage_before,
            "min_voltage_after": res.min_voltage_after,
            "investment_cost_usd": res.estimated_investment_cost,
        }

    def _run_filter_design(self, params: Dict[str, Any]) -> Dict[str, Any]:
        v_kv = float(params.get("nominal_voltage_kv", 13.8))
        f0 = float(params.get("frequency_hz", 60.0))
        s_sc = float(params.get("short_circuit_mva", 200.0))
        target_h = int(params.get("target_harmonic", 5))
        harmonics = params.get("harmonic_currents_a", {5: 40.0, 7: 20.0})

        opt = HarmonicFilterOptimizer(
            nominal_voltage_kv=v_kv,
            system_frequency_hz=f0,
            short_circuit_mva=s_sc,
            harmonic_currents_a=harmonics,
        )
        res = opt.design_filter_for_harmonic(target_harmonic=target_h)
        return {
            "tuned_harmonic": res.harmonic_order,
            "tuned_frequency_hz": res.tuned_frequency_hz,
            "resistance_ohms": res.resistance_ohms,
            "inductance_mh": res.inductance_mh,
            "capacitance_uf": res.capacitance_uf,
            "thd_v_before_pct": res.thd_v_before_pct,
            "thd_v_after_pct": res.thd_v_after_pct,
            "ieee_519_compliant": res.ieee_519_compliant,
            "filter_cost_usd": res.estimated_filter_cost_usd,
        }

    def _run_coordination(self, params: Dict[str, Any]) -> Dict[str, Any]:
        r_up = params.get("upstream_relay")
        r_down = params.get("downstream_relay")
        faults = params.get("fault_currents", [5.0, 10.0])
        margin = float(params.get("target_margin", 0.2))

        opt = PSOCoordinationEngine()
        return opt.optimize_coordination_2d(r_up, r_down, faults, target_margin=margin)

    def _run_opf(self, params: Dict[str, Any]) -> Dict[str, Any]:
        ybus = params.get("ybus")
        bus_ids = params.get("bus_ids")
        costs = params.get("generator_costs")
        gen_buses = params.get("gen_buses")
        load_data = params.get("load_data")

        opt = PSOOptimalPowerFlow(ybus, bus_ids, costs, gen_buses, load_data)
        res = opt.solve()
        return {
            "total_cost_usd": res.objective_value,
            "total_generation_mw": res.total_generation,
            "total_losses_mw": res.total_losses,
            "generator_dispatch": {g: str(v) for g, v in res.generator_dispatch.items()},
            "success": res.success,
        }
