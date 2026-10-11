"""tests/test_mandatory_engineering_inputs.py — Dual Acceptance & Negative Suite for P0-4.

Validates that:
1. No silent synthetic inputs masquerade as authoritative engineering truth.
2. Incomplete-but-non-empty requests are rejected pre-calculation with INSUFFICIENT_ENGINEERING_INPUT.
3. Demo / synthetic mode is only permitted when explicitly requested (e.g. demo=True) and is labeled end-to-end.
4. Simulated SCADA connection cannot report live success; live demands return REAL_INTEGRATION_UNAVAILABLE.
5. Physically invalid inputs (negative/zero/non-finite) are rejected.
6. Complete valid inputs execute successfully.
"""

from __future__ import annotations

import numpy as np
import pytest

from agents.battery_storage_agent import BatteryStorageAgent
from agents.cable_sizing_agent import CableSizingAgent
from agents.earth_grid_agent import EarthGridAgent
from agents.motor_starting_agent import MotorStartingAgent
from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
from agents.renewable_agent import RenewableAgent
from agents.scada_agent import SCADAAgent
from agents.stability_agent import StabilityAgent

# ===========================================================================
# 1. BatteryStorageAgent
# ===========================================================================


@pytest.mark.asyncio
async def test_battery_storage_rejects_incomplete_request():
    """Negative test: Non-empty request missing load_profile_kw and energy_prices must fail."""
    agent = BatteryStorageAgent()
    task = EngineeringTask(
        task_id="bess_incomplete_01",
        description="BESS incomplete test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "full", "max_power_kw": 500},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"
    assert "load_profile_kw" in result.data.get("message", "")


@pytest.mark.asyncio
async def test_battery_storage_rejects_negative_profile():
    """Negative test: Profile containing negative numbers must fail."""
    agent = BatteryStorageAgent()
    task = EngineeringTask(
        task_id="bess_negative_02",
        description="BESS negative test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "sizing",
            "load_profile_kw": [100.0, -50.0, 200.0],
        },
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"


@pytest.mark.asyncio
async def test_battery_storage_explicit_demo_labeled():
    """Demo test: Explicit demo=True allows synthetic data but labels it non-authoritative."""
    agent = BatteryStorageAgent()
    task = EngineeringTask(
        task_id="bess_demo_03",
        description="BESS demo test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "full", "demo": True},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert result.data.get("authoritative") is False
    assert result.data.get("synthetic") is True
    assert result.data.get("demo_mode") is True
    assert result.data.get("provenance", {}).get("authoritative") is False


@pytest.mark.asyncio
async def test_battery_storage_complete_valid_inputs():
    """Positive test: Fully specified load and prices execute as authoritative."""
    agent = BatteryStorageAgent()
    task = EngineeringTask(
        task_id="bess_authoritative_04",
        description="BESS authoritative test",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "full",
            "load_profile_kw": [150.0, 200.0, 300.0, 250.0],
            "energy_prices": [0.10, 0.15, 0.25, 0.12],
            "bess_power_kw": 100.0,
            "bess_energy_kwh": 400.0,
        },
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert result.data.get("authoritative") is True
    assert result.data.get("synthetic") is False


# ===========================================================================
# 2. SCADAAgent
# ===========================================================================


@pytest.mark.asyncio
async def test_scada_rejects_missing_server():
    """Negative test: Non-empty request missing scada_server must fail."""
    agent = SCADAAgent()
    task = EngineeringTask(
        task_id="scada_no_server_01",
        description="SCADA missing server",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "connect"},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"
    assert "scada_server" in result.data.get("message", "")


@pytest.mark.asyncio
async def test_scada_rejects_invalid_port():
    """Negative test: Invalid port must fail."""
    agent = SCADAAgent()
    task = EngineeringTask(
        task_id="scada_bad_port_02",
        description="SCADA bad port",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "connect", "scada_server": "10.0.0.1", "scada_port": 99999},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"


@pytest.mark.asyncio
async def test_scada_rejects_live_demand():
    """Negative test: Demanding live connection returns REAL_INTEGRATION_UNAVAILABLE."""
    agent = SCADAAgent()
    task = EngineeringTask(
        task_id="scada_live_fail_03",
        description="SCADA live demand",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"scada_server": "substation1.grid.local", "require_live": True},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "REAL_INTEGRATION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_scada_simulated_is_labeled():
    """Simulated test: Simulated run succeeds but is explicitly labeled non-authoritative."""
    agent = SCADAAgent()
    task = EngineeringTask(
        task_id="scada_sim_04",
        description="SCADA simulation",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "connect", "scada_server": "substation1.grid.local", "scada_port": 102},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert result.data.get("authoritative") is False
    assert result.data.get("simulated") is True
    assert result.data.get("live_connection") is False


# ===========================================================================
# 3. CableSizingAgent
# ===========================================================================


@pytest.mark.asyncio
async def test_cable_sizing_rejects_incomplete_request():
    """Negative test: Voltage drop missing length and voltage must fail."""
    agent = CableSizingAgent()
    task = EngineeringTask(
        task_id="cable_incomplete_01",
        description="Cable sizing incomplete",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "voltage_drop", "load_current_A": 150.0},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"


@pytest.mark.asyncio
async def test_cable_sizing_rejects_negative_current():
    """Negative test: Non-positive current must fail."""
    agent = CableSizingAgent()
    task = EngineeringTask(
        task_id="cable_negative_02",
        description="Cable sizing negative current",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "voltage_drop",
            "load_current_A": -20.0,
            "cable_length_m": 100.0,
            "system_voltage_V": 400.0,
            "cross_section_mm2": 70,
        },
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"


@pytest.mark.asyncio
async def test_cable_sizing_valid_execution():
    """Positive test: Valid parameters execute successfully."""
    agent = CableSizingAgent()
    task = EngineeringTask(
        task_id="cable_valid_03",
        description="Cable sizing valid",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "voltage_drop",
            "load_current_A": 150.0,
            "cable_length_m": 80.0,
            "system_voltage_V": 400.0,
            "cross_section_mm2": 70,
        },
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert "voltage_drop" in result.data


# ===========================================================================
# 4. EarthGridAgent
# ===========================================================================


@pytest.mark.asyncio
async def test_earth_grid_rejects_incomplete_request():
    """Negative test: Design missing rho_soil and Ig_max must fail."""
    agent = EarthGridAgent()
    task = EngineeringTask(
        task_id="earth_incomplete_01",
        description="Earth grid incomplete",
        study_types=[StudyType.SHORT_CIRCUIT],
        parameters={"analysis_type": "design"},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"


@pytest.mark.asyncio
async def test_earth_grid_valid_execution():
    """Positive test: Complete earth grid parameters execute successfully."""
    agent = EarthGridAgent()
    task = EngineeringTask(
        task_id="earth_valid_02",
        description="Earth grid valid",
        study_types=[StudyType.SHORT_CIRCUIT],
        parameters={
            "analysis_type": "design",
            "rho_soil": 120.0,
            "Ig_max": 4500.0,
            "grid_length_m": 60.0,
            "grid_width_m": 45.0,
        },
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert "grid_design" in result.data


# ===========================================================================
# 5. MotorStartingAgent
# ===========================================================================


@pytest.mark.asyncio
async def test_motor_starting_rejects_incomplete_request():
    """Negative test: Starting current missing motor_hp and voltage_v must fail."""
    agent = MotorStartingAgent()
    task = EngineeringTask(
        task_id="motor_incomplete_01",
        description="Motor starting incomplete",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "starting_current"},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"


@pytest.mark.asyncio
async def test_motor_starting_valid_execution():
    """Positive test: Complete motor parameters execute successfully."""
    agent = MotorStartingAgent()
    task = EngineeringTask(
        task_id="motor_valid_02",
        description="Motor starting valid",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "starting_current",
            "motor_hp": 150.0,
            "voltage_v": 460.0,
            "starting_method": "DOL",
        },
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert "starting_current" in result.data


# ===========================================================================
# 6. RenewableAgent
# ===========================================================================


@pytest.mark.asyncio
async def test_renewable_rejects_incomplete_solar():
    """Negative test: Solar PV missing capacity must fail."""
    agent = RenewableAgent()
    task = EngineeringTask(
        task_id="pv_incomplete_01",
        description="Solar PV incomplete",
        study_types=[StudyType.LOAD_FLOW],
        parameters={"analysis_type": "solar_pv"},
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.FAILED
    assert result.data.get("error_code") == "INSUFFICIENT_ENGINEERING_INPUT"


@pytest.mark.asyncio
async def test_renewable_valid_solar_execution():
    """Positive test: Complete solar capacity executes successfully."""
    agent = RenewableAgent()
    task = EngineeringTask(
        task_id="pv_valid_02",
        description="Solar PV valid",
        study_types=[StudyType.LOAD_FLOW],
        parameters={
            "analysis_type": "solar_pv",
            "pv_dc_capacity_kw": 800.0,
        },
    )
    result = await agent.execute(task)
    assert result.status == AgentStatus.COMPLETED
    assert "solar_pv" in result.data
