"""Stability Agent - Multi-turn Conversation Scenario Test.

Tests the StabilityAgent through multi-turn engineering scenarios covering
transient stability via swing equation, small-signal eigenvalue analysis,
and critical clearing time computation per IEEE 399.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from agents.orchestrator import (
    AgentResult,
    AgentStatus,
    EngineeringTask,
    StudyType,
)
from agents.stability_agent import StabilityAgent


@pytest.fixture
def agent():
    return StabilityAgent()


@pytest.fixture
def smib_params():
    """Single-Machine Infinite Bus parameters for CCT calculation."""
    return {
        "H": 5.0,          # Inertia constant (s)
        "Pm": 0.8,         # Mechanical power (pu)
        "E_gen": 1.1,      # Internal voltage (pu)
        "V_inf": 1.0,      # Infinite bus voltage (pu)
        "X_total": 0.5,    # Pre-fault reactance (pu)
        "X_faulted": 1e6,  # During fault (3ph at terminals)
        "delta0": 0.5,     # Initial angle (rad)
    }


@pytest.fixture
def multimachine_data():
    """3-machine test system data for transient stability."""
    n_gen = 3
    np.random.seed(42)
    G = np.random.uniform(2.0, 8.0, (n_gen, n_gen))
    G = (G + G.T) / 2.0
    B = np.random.uniform(-12.0, -3.0, (n_gen, n_gen))
    B = (B + B.T) / 2.0
    np.fill_diagonal(G, np.sum(G, axis=1) - np.diag(G) + 1.0)
    np.fill_diagonal(B, -np.sum(np.abs(B), axis=1))
    Ybus_red = G + 1j * B

    return {
        "H": np.array([3.0, 4.0, 5.0]),
        "D": np.array([2.0, 2.0, 2.0]),
        "Pm": np.array([0.8, 0.6, 0.5]),
        "Ybus_red": Ybus_red,
        "E": np.array([1.1, 1.0, 1.05]),
        "delta0": np.array([0.3, 0.1, -0.2]),
    }


class TestStabilityScenario:
    """Test Stability Agent with multi-turn engineering scenarios."""

    def test_agent_initialization(self, agent):
        """Test 1: Agent initializes with IEEE 399 standards."""
        assert agent.agent_name == "StabilityAgent"
        assert "IEEE 399-1997" in agent.standards

    def test_transient_stability_analysis(self, agent, multimachine_data):
        """Test 2: Transient stability via RK4 swing equation integration."""
        d = multimachine_data
        fault_Ybus = d["Ybus_red"].copy()
        fault_Ybus[0, 0] += 1.0 / 1e-6  # Three-phase fault at bus 0

        post_fault_Ybus = d["Ybus_red"].copy()

        result = agent.analyze_transient_stability(
            H=d["H"],
            D=d["D"],
            Pm=d["Pm"],
            Ybus_red=d["Ybus_red"],
            E=d["E"],
            delta0=d["delta0"],
            fault_bus=0,
            fault_Ybus=fault_Ybus,
            post_fault_Ybus=post_fault_Ybus,
            t_fault=0.0,
            t_clear=0.15,
            t_total=5.0,
            dt=0.01,
        )
        assert "stable" in result
        assert isinstance(result["stable"], bool)
        assert "delta_deg" in result
        assert "omega_pu" in result
        assert "max_angle_spread_deg" in result

    def test_small_signal_stability(self, agent, multimachine_data):
        """Test 3: Small-signal stability via eigenvalue analysis."""
        d = multimachine_data
        result = agent.analyze_small_signal_stability(
            H=d["H"],
            D=d["D"],
            Pm=d["Pm"],
            Ybus_red=d["Ybus_red"],
            E=d["E"],
            delta0=d["delta0"],
        )
        assert "eigenvalues" in result
        assert "damping_ratios" in result
        assert "frequencies_hz" in result
        assert "stable" in result
        assert isinstance(result["stable"], bool)
        assert "min_damping_ratio" in result

    def test_critical_clearing_time(self, agent, smib_params):
        """Test 4: Critical clearing time via equal area criterion."""
        p = smib_params
        result = agent.critical_clearing_time(
            H=p["H"],
            Pm=p["Pm"],
            E_gen=p["E_gen"],
            V_inf=p["V_inf"],
            X_total=p["X_total"],
            X_faulted=p["X_faulted"],
            delta0=p["delta0"],
        )
        assert "critical_clearing_time_s" in result
        assert "critical_clearing_angle_deg" in result
        assert result["critical_clearing_time_s"] > 0
        assert result["equal_area_method"] == "solved"

    def test_cct_infeasible_high_power(self, agent):
        """Test 5: CCT returns infeasible when Pm > Pmax."""
        result = agent.critical_clearing_time(
            H=5.0,
            Pm=10.0,       # Unrealistically high
            E_gen=1.1,
            V_inf=1.0,
            X_total=0.5,
            X_faulted=1e6,
            delta0=0.5,
        )
        assert result["equal_area_method"] == "infeasible"
        assert result["stable"] is False

    @pytest.mark.asyncio
    async def test_full_analysis_via_execute(self, agent):
        """Test 6: Full stability analysis via execute method."""
        task = EngineeringTask(
            task_id="stab-001",
            description="Full stability analysis",
            study_types=[StudyType.TRANSIENT_STABILITY],
            parameters={"analysis_type": "full"},
        )
        result = await agent.execute(task)
        assert result.status == AgentStatus.COMPLETED
        assert "transient_stability" in result.data
        assert "small_signal_stability" in result.data
        assert "critical_clearing_time" in result.data
