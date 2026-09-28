"""
tests/test_optimization_agent_m3.py — Unit tests for OptimizationAgent compliance & rejection gates (M3.4).

Verifies:
1. ieee_519_compliant == False -> AgentStatus.REJECTED.
2. coordinated == False -> AgentStatus.REJECTED.
3. Configurable seed is recorded in result.data["seed"].
4. Violations list is preserved and validation_status is False on rejected solutions.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

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
