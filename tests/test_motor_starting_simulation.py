"""
tests/test_motor_starting_simulation.py — Dynamic Motor Starting Simulation Suite (IEEE 399).

Validates:
1. Dynamic Runge-Kutta 4th Order (RK4) integration of the motor swing equation:
   J * d(omega)/dt = Te(omega, V) - Tm(omega).
2. Multiple starting methods: Direct-On-Line (DOL), Star-Delta, Soft-Starter, VFD.
3. Transient terminal voltage dip and adjacent bus voltage dip.
4. Stall condition detection under severe load torque / excessive voltage drop.
5. End-to-end integration with MotorStartingAgent.
"""

import pytest

from agents.motor_starting_agent import MotorStartingAgent
from agents.orchestrator import AgentStatus, EngineeringTask, StudyType
from motor_starting.engine import MotorStartingEngine, MotorStartingResult
from motor_starting.motor_models import (
    DynamicMotorParams,
    InductionMotorDynamics,
    LoadProfile,
    MechanicalLoadModel,
    StartingMethod,
)


class TestDynamicMotorStarting:
    """Test suite for IEEE 399 dynamic time-domain motor starting simulator."""

    @pytest.fixture
    def standard_motor_params(self):
        return DynamicMotorParams(
            motor_id="M_PUMP_100HP",
            rated_hp=100.0,
            rated_kv=0.460,
            rated_rpm=1780.0,
            poles=4,
            frequency_hz=60.0,
            inertia_j_motor=1.5,
            inertia_j_load=3.0,
            r_stator=0.025,
            x_stator=0.090,
            r_rotor=0.030,
            x_rotor=0.090,
            x_magnetizing=3.2,
        )

    def test_dol_starting_acceleration(self, standard_motor_params):
        """Test DOL starting: accelerates to rated speed with transient inrush current."""
        load = MechanicalLoadModel(profile=LoadProfile.QUADRATIC, t_breakaway_pu=0.20, t_rated_pu=0.85)
        engine = MotorStartingEngine(
            motor_params=standard_motor_params,
            load_model=load,
            source_impedance=complex(0.01, 0.04),
            starting_method=StartingMethod.DOL,
        )
        result = engine.simulate(t_max_s=8.0, dt_s=0.005)

        assert isinstance(result, MotorStartingResult)
        assert result.successful_start is True, f"DOL starting failed: {result.status_message}"
        assert 0.4 < result.acceleration_time_s < 4.0, f"Unreasonable accel time: {result.acceleration_time_s}s"
        assert result.stall_detected is False
        assert result.peak_starting_current_pu > 3.5, "DOL starting inrush should exceed 3.5 pu"
        assert result.max_voltage_dip_pct > 0.0, "Voltage dip must be positive"
        assert result.final_speed_rpm > 1700.0, "Final speed should approach rated speed"

    def test_star_delta_starting_reduces_inrush_and_dip(self, standard_motor_params):
        """Test Star-Delta starting reduces inrush current and voltage dip compared to DOL."""
        load = MechanicalLoadModel(profile=LoadProfile.QUADRATIC, t_breakaway_pu=0.15, t_rated_pu=0.60)
        source_z = complex(0.015, 0.06)

        # 1. Run DOL
        engine_dol = MotorStartingEngine(
            motor_params=standard_motor_params,
            load_model=load,
            source_impedance=source_z,
            starting_method=StartingMethod.DOL,
        )
        res_dol = engine_dol.simulate(t_max_s=8.0, dt_s=0.005)

        # 2. Run Star-Delta
        engine_sd = MotorStartingEngine(
            motor_params=standard_motor_params,
            load_model=load,
            source_impedance=source_z,
            starting_method=StartingMethod.STAR_DELTA,
            transition_time_s=2.5,
        )
        res_sd = engine_sd.simulate(t_max_s=8.0, dt_s=0.005)

        assert res_sd.successful_start is True
        # Star-Delta inrush current must be significantly lower than DOL
        assert res_sd.peak_starting_current_pu < res_dol.peak_starting_current_pu
        # Voltage dip with Star-Delta must be significantly milder
        assert res_sd.max_voltage_dip_pct < res_dol.max_voltage_dip_pct

    def test_soft_starter_ramping(self, standard_motor_params):
        """Test Soft-Starter ramps voltage smoothly, moderating current surges."""
        load = MechanicalLoadModel(profile=LoadProfile.QUADRATIC, t_breakaway_pu=0.15, t_rated_pu=0.75)
        engine = MotorStartingEngine(
            motor_params=standard_motor_params,
            load_model=load,
            source_impedance=complex(0.01, 0.04),
            starting_method=StartingMethod.SOFT_STARTER,
            soft_start_ramp_time_s=3.0,
            soft_start_initial_voltage=0.35,
        )
        result = engine.simulate(t_max_s=8.0, dt_s=0.005)

        assert result.successful_start is True
        assert len(result.trajectory.voltage_pu) > 100
        # Voltage at beginning is soft-started below nominal
        v_start = result.trajectory.voltage_pu[0]
        v_end = result.trajectory.voltage_pu[-1]
        assert v_start < v_end

    def test_adjacent_bus_voltage_dip_tracking(self, standard_motor_params):
        """Test multi-bus tracking propagates voltage dip to adjacent buses."""
        engine = MotorStartingEngine(
            motor_params=standard_motor_params,
            source_impedance=complex(0.01, 0.05),
            starting_method=StartingMethod.DOL,
        )
        # Add adjacent bus (MCC-2) with 70% voltage sensitivity to motor bus
        engine.add_adjacent_bus("MCC-2", transfer_impedance_ratio=complex(0.70, 0.0))
        result = engine.simulate(t_max_s=5.0, dt_s=0.01)

        assert "MCC-2" in result.trajectory.bus_voltages_pu
        mcc2_voltages = result.trajectory.bus_voltages_pu["MCC-2"]
        assert len(mcc2_voltages) > 0
        min_mcc2_v = min(mcc2_voltages)
        # Dip at MCC-2 should be present but less severe than motor terminals
        assert min_mcc2_v < 1.0
        assert min_mcc2_v > result.min_voltage_pu

    def test_motor_stall_under_excessive_load(self, standard_motor_params):
        """Test that excessive load torque causes motor to stall with safety detection."""
        # Unreasonable load: 3.5 pu torque (higher than motor breakdown torque 2.4 pu)
        heavy_load = MechanicalLoadModel(profile=LoadProfile.CONSTANT, t_rated_pu=3.5)
        engine = MotorStartingEngine(
            motor_params=standard_motor_params,
            load_model=heavy_load,
            source_impedance=complex(0.02, 0.08),
            starting_method=StartingMethod.DOL,
        )
        result = engine.simulate(t_max_s=4.0, dt_s=0.01)

        assert result.successful_start is False
        assert result.stall_detected is True
        assert "STALLED" in result.status_message

    @pytest.mark.asyncio
    async def test_agent_dynamic_simulation_dispatch(self):
        """Test MotorStartingAgent executes dynamic RK4 simulation and includes trajectory metrics."""
        agent = MotorStartingAgent()
        task = EngineeringTask(
            task_id="ms-dyn-01",
            description="Dynamic Motor Starting Study",
            study_types=[StudyType.MOTOR_STARTING],
            parameters={
                "analysis_type": "dynamic",
                "motor_hp": 150.0,
                "voltage_v": 460.0,
                "rated_speed_rpm": 1780.0,
                "starting_method": "DOL",
                "j_total_kgm2": 8.0,
                "source_impedance_r_pu": 0.01,
                "source_impedance_x_pu": 0.04,
            },
        )
        agent_res = await agent.execute(task)
        assert agent_res.status == AgentStatus.COMPLETED
        assert "dynamic_simulation" in agent_res.data
        dyn_data = agent_res.data["dynamic_simulation"]
        assert dyn_data["successful_start"] is True
        assert dyn_data["acceleration_time_s"] > 0
        assert dyn_data["peak_starting_current_a"] > 0
        assert dyn_data["max_voltage_dip_pct"] > 0
