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
            "enclosure_type": "box",
            "enclosure_width_mm": 508.0,
            "enclosure_height_mm": 508.0,
            "enclosure_depth_mm": 508.0,
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
            enclosure_type=params["enclosure_type"],
            enclosure_width_mm=params["enclosure_width_mm"],
            enclosure_height_mm=params["enclosure_height_mm"],
            enclosure_depth_mm=params["enclosure_depth_mm"],
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

    async def test_missing_electrode_config_fails_closed(self):
        """Missing electrode_config must not silently default to VCB."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_no_elec",
            description="Arc flash missing electrode_config",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.1,
                "working_distance_mm": 457.0,
                "arc_gap_mm": 25.0,
                "enclosure_type": "box",
                "enclosure_width_mm": 508.0,
                "enclosure_height_mm": 508.0,
                "enclosure_depth_mm": 508.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("electrode_config" in err for err in res.validation_errors)

    async def test_missing_box_dimensions_fails_closed(self):
        """Missing enclosure dimensions when enclosure_type=box must not silently default to 508mm."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_no_dims",
            description="Arc flash missing box dims",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.1,
                "working_distance_mm": 457.0,
                "electrode_config": "VCB",
                "enclosure_type": "box",
                "arc_gap_mm": 25.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("enclosure_width_mm" in err for err in res.validation_errors)

    async def test_nonfinite_parameter_fails_closed(self):
        """Nonfinite parameters (NaN, inf) must fail closed."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_nan",
            description="Arc flash NaN parameter",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "voltage_kv": float("nan"),
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.1,
                "working_distance_mm": 457.0,
                "electrode_config": "VCB",
                "enclosure_type": "box",
                "enclosure_width_mm": 508.0,
                "enclosure_height_mm": 508.0,
                "enclosure_depth_mm": 508.0,
                "arc_gap_mm": 25.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("voltage_kv" in err for err in res.validation_errors)

    async def test_invalid_analysis_type_fails_closed(self):
        """Invalid analysis_type must be rejected."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_bad_type",
            description="Arc flash bad analysis type",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "analysis_type": "speculative_estimate",
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 20.0,
                "arc_duration_s": 0.1,
                "working_distance_mm": 457.0,
                "electrode_config": "VCB",
                "enclosure_type": "box",
                "enclosure_width_mm": 508.0,
                "enclosure_height_mm": 508.0,
                "enclosure_depth_mm": 508.0,
                "arc_gap_mm": 25.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.FAILED
        assert any("analysis_type" in err for err in res.validation_errors)

    async def test_arc_current_only_analysis_succeeds_without_duration_or_distance(self):
        """When analysis_type='arc_current', calculation succeeds without duration or distance."""
        agent = ArcFlashAgent()
        task = EngineeringTask(
            task_id="task_af_current_only",
            description="Arc flash arc_current only",
            study_types=[StudyType.ARC_FLASH],
            parameters={
                "analysis_type": "arc_current",
                "voltage_kv": 0.48,
                "bolted_fault_current_ka": 25.0,
                "electrode_config": "VCB",
                "arc_gap_mm": 25.0,
            },
        )
        res = await agent.execute(task)
        assert res.status == AgentStatus.COMPLETED
        assert res.data["arc_current_ka"] > 0
        assert "incident_energy" not in res.data

    def test_study_executor_missing_electrode_config_fails_closed(self):
        """StudyExecutor._dispatch must reject arc flash without electrode_config (no silent VCB)."""
        from services.study_executor import StudyExecutor
        executor = StudyExecutor()
        with pytest.raises(ValueError, match="Missing required arc flash parameter"):
            executor._dispatch(
                "arc_flash",
                None,
                {
                    "voltage_kv": 0.48,
                    "bolted_fault_current_ka": 25.0,
                    "arc_duration_sec": 0.15,
                    "working_distance_mm": 457.0,
                    "arc_gap_mm": 25.0,
                    "enclosure_type": "box",
                    "enclosure_width_mm": 508.0,
                    "enclosure_height_mm": 508.0,
                    "enclosure_depth_mm": 508.0,
                },
            )

    def test_study_executor_missing_box_dims_fails_closed(self):
        """StudyExecutor._dispatch must reject box enclosure without dimensions (no silent 508mm)."""
        from services.study_executor import StudyExecutor
        executor = StudyExecutor()
        with pytest.raises(ValueError, match="Missing required arc flash parameter"):
            executor._dispatch(
                "arc_flash",
                None,
                {
                    "voltage_kv": 0.48,
                    "bolted_fault_current_ka": 25.0,
                    "arc_duration_sec": 0.15,
                    "working_distance_mm": 457.0,
                    "arc_gap_mm": 25.0,
                    "electrode_config": "VCB",
                    "enclosure_type": "box",
                },
            )

    def test_study_service_missing_electrode_config_fails_closed(self):
        """study_service._run_native_study must reject arc flash missing electrode_config."""
        from services.study_service import _run_native_study
        with pytest.raises(ValueError, match="Missing required arc flash parameter"):
            _run_native_study(
                study_type="arc_flash",
                system=None,
                parameters={
                    "voltage_kv": 0.48,
                    "bolted_fault_current_ka": 25.0,
                    "arc_duration_sec": 0.15,
                    "working_distance_mm": 457.0,
                    "arc_gap_mm": 25.0,
                    "enclosure_type": "box",
                    "enclosure_width_mm": 508.0,
                    "enclosure_height_mm": 508.0,
                    "enclosure_depth_mm": 508.0,
                },
            )

    def test_engine_nonfinite_gap_nan_inf_fails_closed(self):
        """ArcFlashEngine.calculate_incident_energy must reject NaN, +inf, -inf conductor gap."""
        for bad_gap in (float("nan"), float("inf"), float("-inf"), -5.0, 0.0):
            with pytest.raises(ValueError, match="arc_gap_mm must be a positive finite number"):
                ArcFlashEngine.calculate_incident_energy(
                    voltage_kv=0.48,
                    bolted_fault_current_ka=25.0,
                    arc_duration_sec=0.15,
                    working_distance_mm=457.0,
                    electrode_config="VCB",
                    enclosure_type="box",
                    enclosure_width_mm=508.0,
                    enclosure_height_mm=508.0,
                    enclosure_depth_mm=508.0,
                    arc_gap_mm=bad_gap,
                )

    def test_engine_nonfinite_duration_and_distance_fails_closed(self):
        """ArcFlashEngine must reject nonfinite duration and working distance without clamping."""
        with pytest.raises(ValueError, match="arc_duration_sec must be a positive finite number"):
            ArcFlashEngine.calculate_incident_energy(
                voltage_kv=0.48,
                bolted_fault_current_ka=25.0,
                arc_duration_sec=float("nan"),
                working_distance_mm=457.0,
                electrode_config="VCB",
                enclosure_type="box",
                enclosure_width_mm=508.0,
                enclosure_height_mm=508.0,
                enclosure_depth_mm=508.0,
                arc_gap_mm=25.0,
            )

        with pytest.raises(ValueError, match="working_distance_mm must be a positive finite number"):
            ArcFlashEngine.calculate_incident_energy(
                voltage_kv=0.48,
                bolted_fault_current_ka=25.0,
                arc_duration_sec=0.15,
                working_distance_mm=float("-inf"),
                electrode_config="VCB",
                enclosure_type="box",
                enclosure_width_mm=508.0,
                enclosure_height_mm=508.0,
                enclosure_depth_mm=508.0,
                arc_gap_mm=25.0,
            )

    def test_engine_invalid_electrode_and_enclosure_fails_closed(self):
        """ArcFlashEngine must not silently map invalid electrode to VCB or enclosure to BOX."""
        with pytest.raises(ValueError, match="Invalid electrode_config"):
            ArcFlashEngine.calculate_incident_energy(
                voltage_kv=0.48,
                bolted_fault_current_ka=25.0,
                arc_duration_sec=0.15,
                working_distance_mm=457.0,
                electrode_config="NOT_A_CONFIG",
                enclosure_type="box",
                enclosure_width_mm=508.0,
                enclosure_height_mm=508.0,
                enclosure_depth_mm=508.0,
                arc_gap_mm=25.0,
            )

        with pytest.raises(ValueError, match="Invalid enclosure_type"):
            ArcFlashEngine.calculate_incident_energy(
                voltage_kv=0.48,
                bolted_fault_current_ka=25.0,
                arc_duration_sec=0.15,
                working_distance_mm=457.0,
                electrode_config="VCB",
                enclosure_type="SUBMERGED",
                enclosure_width_mm=508.0,
                enclosure_height_mm=508.0,
                enclosure_depth_mm=508.0,
                arc_gap_mm=25.0,
            )

    def test_agent_calculate_incident_energy_invalid_inputs_fail(self):
        """ArcFlashAgent.calculate_incident_energy must reject invalid electrode or out-of-range gap."""
        agent = ArcFlashAgent()
        with pytest.raises(ValueError, match="Invalid electrode_config"):
            agent.calculate_incident_energy(
                voltage_kv=0.48,
                arc_current_ka=20.0,
                arc_duration_s=0.15,
                working_distance_mm=457.0,
                electrode_config="XYZ",
                gap_mm=25.0,
            )

        with pytest.raises(ValueError, match="gap_mm"):
            agent.calculate_incident_energy(
                voltage_kv=0.48,
                arc_current_ka=20.0,
                arc_duration_s=0.15,
                working_distance_mm=457.0,
                electrode_config="VCB",
                gap_mm=2.0,  # Below 6.35 mm minimum for LV
            )
