"""Regression tests for Defect 4: Arc Flash Calculation Unification and Zero Silent Defaults.

Verifies:
1. ArcFlashAgent fails closed when mandatory parameters are missing (no silent defaults).
2. ArcFlashAgent delegates to central ArcFlashEngine.
3. Equivalence between direct PowerSystemEngine / ArcFlashEngine calculations and ArcFlashAgent.execute.
4. Input bounds rejection per IEEE 1584-2018.
"""

from __future__ import annotations

import pytest

from agents.arc_flash_agent import ArcFlashAgent
from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
from engine.engine import PowerSystemEngine
from fault_analysis.arc_flash_engine import ArcFlashEngine


@pytest.mark.asyncio
class TestArcFlashUnification:
    """Verifies central ArcFlashEngine unification and strict parameter gating."""

    async def test_missing_voltage_fails_closed(self):
        """Missing voltage_kv must fail closed without silent default injection."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_missing_v",
            description="Arc flash missing voltage",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "bolted_fault_current_ka": 25.0,
                "arc_duration_s": 0.2,
                "working_distance_mm": 457.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("voltage_kv" in err for err in res.validation_errors)

    async def test_missing_fault_current_fails_closed(self):
        """Missing fault current must fail closed."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_missing_bf",
            description="Arc flash missing fault current",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "arc_duration_s": 0.2,
                "working_distance_mm": 457.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("bolted_fault_current_ka" in err for err in res.validation_errors)

    async def test_missing_duration_fails_closed(self):
        """Missing arc duration must fail closed."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_missing_dur",
            description="Arc flash missing duration",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "working_distance_mm": 457.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("arc_duration_s" in err for err in res.validation_errors)

    async def test_missing_working_distance_fails_closed(self):
        """Missing working distance must fail closed."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_missing_dist",
            description="Arc flash missing distance",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.2,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("working_distance_mm" in err for err in res.validation_errors)

    async def test_agent_and_central_engine_results_agree(self):
        """ArcFlashAgent.execute results must match central ArcFlashEngine / PowerSystemEngine."""
        params = {
            "voltage_kv": 0.48,
            "bolted_fault_current_ka": 25.0,
            "arc_duration_s": 0.15,
            "working_distance_mm": 457.0,
            "electrode_config": "VCB",
            "gap_mm": 25.0,
            "arc_gap_mm": 25.0,
        }

        # Central engine calculation
        pse = PowerSystemEngine()
        engine_res = pse.run_arc_flash(
            voltage_kv=params["voltage_kv"],
            bolted_fault_current_ka=params["bolted_fault_current_ka"],
            arc_duration_sec=params["arc_duration_s"],
            working_distance_mm=params["working_distance_mm"],
            electrode_config=params["electrode_config"],
            arc_gap_mm=params["arc_gap_mm"],
        )

        # Agent execution
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_match",
            description="Arc flash unified run",
            study_types=[StudyType.ARC_FLASH],
            parameters=params,
        )
        agent_res = await agent.execute(task)
        assert agent_res.status == AgentStatus.COMPLETED

        data = agent_res.data
        agent_iarc = data["arc_current"]["arc_current_ka"]
        agent_ie = data["incident_energy"]["incident_energy_cal_cm2"]

        assert abs(agent_iarc - engine_res["arc_current_ka"]) < 1e-4
        assert abs(agent_ie - engine_res["incident_energy_cal_per_cm2"]) < 1e-2

    async def test_arc_current_delegation_matches_central_engine(self):
        """Direct calculate_arc_current on agent must strictly match ArcFlashEngine."""
        agent = ArcFlashAgent()
        v_kv = 0.48
        ibf = 30.0

        agent_arc = agent.calculate_arc_current(voltage_kv=v_kv, bolted_fault_current_ka=ibf)
        central_iarc, central_reduced = ArcFlashEngine.calculate_arc_current(
            voltage_kv=v_kv,
            bolted_fault_current_ka=ibf,
            electrode_config="VCB",
        )

        assert abs(agent_arc["arc_current_ka"] - central_iarc) < 1e-4
        assert abs(agent_arc["reduced_arc_current_ka"] - central_reduced) < 1e-4

    async def test_missing_arc_gap_fails_closed(self):
        """Missing arc_gap_mm must fail closed without fallback to silent default 32.0 mm."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_missing_gap",
            description="Arc flash missing gap",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.2,
                "working_distance_mm": 457.0,
                "electrode_config": "VCB",
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("arc_gap_mm" in err for err in res.validation_errors)

    async def test_zero_or_negative_arc_duration_fails_closed(self):
        """Zero duration must not be silently replaced by a default duration."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_zero_dur",
            description="Arc flash zero duration",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.0,
                "working_distance_mm": 457.0,
                "electrode_config": "VCB",
                "arc_gap_mm": 25.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("arc_duration_s" in err for err in res.validation_errors)

    async def test_invalid_electrode_config_fails_closed(self):
        """Invalid electrode configuration must not silently coerce to VCB."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_bad_elec",
            description="Arc flash invalid electrode",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.1,
                "working_distance_mm": 457.0,
                "electrode_config": "NON_EXISTENT_CFG",
                "arc_gap_mm": 25.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("electrode_config" in err for err in res.validation_errors)

    async def test_invalid_enclosure_type_fails_closed(self):
        """Invalid enclosure type must not silently coerce to BOX."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_bad_enc",
            description="Arc flash invalid enclosure",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.1,
                "working_distance_mm": 457.0,
                "electrode_config": "VCB",
                "arc_gap_mm": 25.0,
                "enclosure_type": "MY_FANCY_ENCLOSURE",
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("enclosure_type" in err for err in res.validation_errors)
