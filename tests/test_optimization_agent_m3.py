"""
tests/test_optimization_agent_m3.py — Unit tests for OptimizationAgent compliance & rejection gates (M3.4).

Verifies:
1. ieee_519_compliant == False -> AgentStatus.REJECTED.
2. coordinated == False -> AgentStatus.REJECTED.
3. Configurable seed is recorded in result.data["seed"].
4. Violations list is preserved and validation_status is False on rejected solutions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.models import AgentStatus, EngineeringTask, StudyType
from agents.optimizers.optimization_agent import OptimizationAgent


@pytest.mark.asyncio
async def test_optimization_agent_ieee_519_violation_triggers_rejected():
    """Witness M3.4: Non-compliant harmonic filter must yield AgentStatus.REJECTED."""
    agent = OptimizationAgent()
    task = EngineeringTask(
        task_id="opt_filter_fail",
        description="Filter design violating IEEE 519",
        study_types=[StudyType.OPTIMAL_POWER_FLOW],
        parameters={
            "optimization_type": "harmonic_filter",
            "seed": 1234,
        },
    )

    mock_res = {
        "ieee_519_compliant": False,
        "thd_v_after_pct": 7.8,
        "thd_v_before_pct": 12.0,
        "filter_specs": {"type": "single_tuned", "c_mvar": 5.0},
    }

    with patch.object(agent, "_run_filter_design", return_value=mock_res):
        result = await agent.execute(task)

    assert result.status == AgentStatus.REJECTED
    assert result.validation_status is False
    assert result.data["seed"] == 1234
    assert len(result.data["violations"]) > 0
    assert any("IEEE 519" in v for v in result.validation_errors)


@pytest.mark.asyncio
async def test_optimization_agent_protection_uncoordinated_triggers_rejected():
    """Witness M3.4: Protection coordination failing time margin must yield AgentStatus.REJECTED."""
    agent = OptimizationAgent()
    task = EngineeringTask(
        task_id="opt_prot_fail",
        description="Relay coordination margin violation",
        study_types=[StudyType.OPTIMAL_POWER_FLOW],
        parameters={
            "optimization_type": "protection_coordination",
            "seed": 99,
        },
    )

    mock_res = {
        "coordinated": False,
        "success": False,
        "cpi": 0.45,
        "miscoordinations": ["Relay R1 and R2 time margin 0.12s < 0.20s"],
    }

    with patch.object(agent, "_run_coordination", return_value=mock_res):
        result = await agent.execute(task)

    assert result.status == AgentStatus.REJECTED
    assert result.validation_status is False
    assert result.data["seed"] == 99
    assert len(result.data["violations"]) > 0
    assert any("coordination failed" in v for v in result.validation_errors)


@pytest.mark.asyncio
async def test_optimization_agent_success_records_seed_and_completed():
    """Witness M3.4: Compliant optimization yields COMPLETED with recorded seed."""
    agent = OptimizationAgent()
    task = EngineeringTask(
        task_id="opt_filter_success",
        description="Compliant harmonic filter design",
        study_types=[StudyType.OPTIMAL_POWER_FLOW],
        parameters={
            "optimization_type": "harmonic_filter",
            "seed": 777,
        },
    )

    mock_res = {
        "ieee_519_compliant": True,
        "thd_v_after_pct": 3.2,
        "thd_v_before_pct": 11.5,
        "filter_specs": {"type": "single_tuned", "c_mvar": 8.0},
    }

    with patch.object(agent, "_run_filter_design", return_value=mock_res):
        result = await agent.execute(task)

    assert result.status == AgentStatus.COMPLETED
    assert result.validation_status is True
    assert result.data["seed"] == 777
    assert result.data["violations"] == []


@pytest.mark.asyncio
async def test_optimization_agent_passes_seed_to_all_pso_engines():
    """Witness M3.4: Prove that configurable seed is actually propagated to all 4 PSO engines."""
    agent = OptimizationAgent()

    # 1. Placement engine receives seed
    with patch("agents.optimizers.optimization_agent.OptimalPlacementPSO") as mock_placement:
        mock_instance = MagicMock()
        mock_instance.optimize_capacitor_placement.return_value = MagicMock(
            optimal_allocations={},
            initial_losses_mw=1.2,
            optimized_losses_mw=0.9,
            loss_reduction_pct=25.0,
            min_voltage_before=0.93,
            min_voltage_after=0.98,
            estimated_investment_cost=15000.0,
        )
        mock_placement.return_value = mock_instance

        task_placement = EngineeringTask(
            task_id="opt_seed_placement",
            description="Placement with custom seed",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "placement", "seed": 333, "bus_ids": [1, 2]},
        )
        res = await agent.execute(task_placement)
        assert res.data["seed"] == 333
        mock_placement.assert_called_once()
        assert mock_placement.call_args[1].get("seed") == 333

    # 2. Filter design engine receives seed
    with patch("agents.optimizers.optimization_agent.HarmonicFilterOptimizer") as mock_filter:
        mock_instance = MagicMock()
        mock_instance.design_filter_for_harmonic.return_value = MagicMock(
            harmonic_order=5,
            tuned_frequency_hz=300.0,
            resistance_ohms=0.5,
            inductance_mh=12.0,
            capacitance_uf=30.0,
            thd_v_before_pct=8.0,
            thd_v_after_pct=3.0,
            ieee_519_compliant=True,
            estimated_filter_cost_usd=20000.0,
        )
        mock_filter.return_value = mock_instance

        task_filter = EngineeringTask(
            task_id="opt_seed_filter",
            description="Filter with custom seed",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "filter_design", "seed": 444},
        )
        res = await agent.execute(task_filter)
        assert res.data["seed"] == 444
        mock_filter.assert_called_once()
        assert mock_filter.call_args[1].get("seed") == 444

    # 3. Coordination engine receives seed
    with patch("agents.optimizers.optimization_agent.PSOCoordinationEngine") as mock_coord:
        mock_instance = MagicMock()
        mock_instance.optimize_coordination_2d.return_value = {
            "coordinated": True,
            "success": True,
            "cpi": 0.95,
        }
        mock_coord.return_value = mock_instance

        task_coord = EngineeringTask(
            task_id="opt_seed_coord",
            description="Coordination with custom seed",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "protection_coordination", "seed": 555},
        )
        res = await agent.execute(task_coord)
        assert res.data["seed"] == 555
        mock_coord.assert_called_once_with(seed=555)

    # 4. OPF engine receives seed
    with patch("agents.optimizers.optimization_agent.PSOOptimalPowerFlow") as mock_opf:
        mock_instance = MagicMock()
        mock_instance.solve.return_value = MagicMock(
            objective_value=12500.0,
            total_generation=150.0,
            total_losses=4.5,
            generator_dispatch={},
            success=True,
        )
        mock_opf.return_value = mock_instance

        task_opf = EngineeringTask(
            task_id="opt_seed_opf",
            description="OPF with custom seed",
            study_types=[StudyType.OPTIMAL_POWER_FLOW],
            parameters={"optimization_type": "pso_opf", "seed": 666, "generator_costs": []},
        )
        res = await agent.execute(task_opf)
        assert res.data["seed"] == 666
        mock_opf.assert_called_once()
        assert mock_opf.call_args[1].get("seed") == 666

