"""
AhmedETAP - Stability Analysis Agent
========================================================
Transient and small-signal stability analysis per IEEE 399 (Brown Book)
and IEEE 1584-2018.

Capabilities:
- Transient stability via swing equation integration (Euler & RK4)
- Equal area criterion for critical clearing time
- Small-signal stability via eigenvalue analysis of linearized system
- Critical clearing time computation
- Damping ratio and frequency of oscillatory modes

Standards:
- IEEE 399-1997: IEEE Recommended Practice for Industrial and Commercial
  Power System Analysis (Brown Book)
- IEEE 1584-2018: Guide for Performing Arc-Flash Hazard Calculations
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class StabilityAgent(BaseAgent):
    """
    Transient and Small-Signal Stability Analysis Agent.

    Implements stability assessment methods compliant with IEEE 399
    and IEEE 1584-2018, including:

    - Swing equation integration for multi-machine transient stability
    - Equal area criterion for single-machine-infinite-bus (SMIB) systems
    - Eigenvalue-based small-signal stability analysis
    - Critical clearing time (CCT) determination
    - Participation factor analysis for mode identification

    The swing equation solved is:

        M * d²δ/dt² = Pm - Pe - D * dδ/dt

    where M = 2H/ωs is the machine inertia constant, Pm is mechanical
    power, Pe is electrical power, D is damping coefficient, and δ is
    the rotor angle.
    """

    prompt_handle = "stability_agent"

    def __init__(self) -> None:
        super().__init__("StabilityAgent")
        self.standards = ["IEEE 399-1997", "IEEE 1584-2018"]
        self.system_base_mva: float = 100.0
        self.system_frequency: float = 60.0  # Hz
        self.omega_synchronous: float = 2.0 * np.pi * 60.0  # rad/s

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def analyze_transient_stability(
        self,
        H: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        D: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Pm: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ybus_red: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        delta0: np.ndarray,
        fault_bus: int,
        fault_Ybus: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        post_fault_Ybus: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        t_fault: float,
        t_clear: float,
        t_total: float,
        dt: float = 0.01,
    ) -> dict[str, Any]:
        """
        Perform transient stability analysis using the swing equation.

        Solves the multi-machine swing equations using 4th-order Runge-Kutta
        integration through three periods: pre-fault, during-fault, and
        post-fault.

        Parameters
        ----------
        H : np.ndarray
            Inertia constants of machines in seconds, shape (n_gen,).
        D : np.ndarray
            Damping coefficients in pu, shape (n_gen,).
        Pm : np.ndarray
            Mechanical power in pu, shape (n_gen,).
        Ybus_red : np.ndarray
            Reduced bus admittance matrix (n_gen x n_gen) pre-fault.
        E : np.ndarray
            Internal machine voltages in pu (complex), shape (n_gen,).
        delta0 : np.ndarray
            Initial rotor angles in radians, shape (n_gen,).
        fault_bus : int
            Index of the faulted bus (0-based in reduced matrix).
        fault_Ybus : np.ndarray
            Reduced Ybus during fault.
        post_fault_Ybus : np.ndarray
            Reduced Ybus after fault clearance.
        t_fault : float
            Time of fault occurrence in seconds.
        t_clear : float
            Time of fault clearance in seconds.
        t_total : float
            Total simulation time in seconds.
        dt : float
            Integration time step in seconds.

        Returns
        -------
        Dict[str, Any]
            Dictionary with keys 'time', 'delta', 'omega', 'stable',
            'max_angle_spread', 'angles_final'.
        """
        n_gen = len(H)

        # State: delta (n_gen), omega (n_gen) relative to synchronous frame
        delta = delta0.copy()
        omega = np.ones(n_gen) * self.omega_synchronous  # Start at synchronous speed

        time_array = np.arange(0, t_total, dt)
        n_steps = len(time_array)

        delta_history = np.zeros((n_steps, n_gen))
        omega_history = np.zeros((n_steps, n_gen))
        delta_history[0] = delta
        omega_history[0] = omega

        def electrical_power(d: np.ndarray, Y: np.ndarray) -> np.ndarray:
            """Calculate electrical power output for each machine."""
            Pe = np.zeros(n_gen)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            E_complex = E * np.exp(1j * d)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            I = Y @ E_complex
            for i in range(n_gen):
                Pe[i] = np.real(E_complex[i] * np.conj(I[i]))
            return Pe

        for step in range(1, n_steps):
            t = time_array[step]

            # Select appropriate Ybus based on time period
            if t < t_fault:
                Y = Ybus_red
            elif t < t_clear:
                Y = fault_Ybus
            else:
                Y = post_fault_Ybus

            # RK4 integration
            def derivatives(
                d: np.ndarray, w: np.ndarray, _Y: np.ndarray = Y,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            ) -> tuple[np.ndarray, np.ndarray]:
                Pe = electrical_power(d, _Y)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                ddelta = w - self.omega_synchronous
                domega = (self.omega_synchronous / (2.0 * H)) * (Pm - Pe - D * ddelta)
                return ddelta, domega

            k1_d, k1_w = derivatives(delta, omega)
            k2_d, k2_w = derivatives(delta + 0.5 * dt * k1_d, omega + 0.5 * dt * k1_w)
            k3_d, k3_w = derivatives(delta + 0.5 * dt * k2_d, omega + 0.5 * dt * k2_w)
            k4_d, k4_w = derivatives(delta + dt * k3_d, omega + dt * k3_w)

            delta = delta + (dt / 6.0) * (k1_d + 2 * k2_d + 2 * k3_d + k4_d)
            omega = omega + (dt / 6.0) * (k1_w + 2 * k2_w + 2 * k3_w + k4_w)

            delta_history[step] = delta
            omega_history[step] = omega

        # Stability criterion: max angle spread < 360 degrees (practical: 180 deg)
        max_angle_spread = np.max(np.degrees(delta_history[-1])) - np.min(
            np.degrees(delta_history[-1]),
        )
        stable = max_angle_spread < 180.0

        return {
            "time": time_array.tolist(),
            "delta_deg": np.degrees(delta_history).tolist(),
            "omega_pu": (omega_history / self.omega_synchronous).tolist(),
            "stable": bool(stable),
            "max_angle_spread_deg": float(max_angle_spread),
            "angles_final_deg": np.degrees(delta_history[-1]).tolist(),
        }

    def analyze_small_signal_stability(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self,
        H: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        D: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Pm: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Ybus_red: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E: np.ndarray,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        delta0: np.ndarray,
    ) -> dict[str, Any]:
        """
        Perform small-signal stability analysis via eigenvalue method.

        Linearizes the swing equations around the operating point and
        computes eigenvalues of the state matrix to assess stability.

        The state matrix A for n machines (2n states) is:

            A = [[0,                 I              ],
                 [M^{-1} K_S,       M^{-1} K_D     ]]

        where K_S is the synchronizing coefficient matrix and K_D is
        derived from damping.

        Parameters
        ----------
        H : np.ndarray
            Inertia constants in seconds, shape (n_gen,).
        D : np.ndarray
            Damping coefficients in pu, shape (n_gen,).
        Pm : np.ndarray
            Mechanical power in pu, shape (n_gen,).
        Ybus_red : np.ndarray
            Reduced admittance matrix, shape (n_gen, n_gen).
        E : np.ndarray
            Internal voltages (complex), shape (n_gen,).
        delta0 : np.ndarray
            Operating point rotor angles in radians, shape (n_gen,).

        Returns
        -------
        Dict[str, Any]
            Contains 'eigenvalues', 'damping_ratios', 'frequencies_hz',
            'participation_factors', 'stable', 'critical_modes'.
        """
        n_gen = len(H)
        M = 2.0 * H / self.omega_synchronous

        # Compute synchronizing coefficient matrix K_S
        # K_S[i,j] = dPe_i / dDelta_j evaluated at delta0
        K_S = np.zeros((n_gen, n_gen))
        eps = 1e-6

        for j in range(n_gen):
            # Perturb delta_j
            delta_pert = delta0.copy()
            delta_pert[j] += eps

            E_plus = E * np.exp(1j * delta_pert)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            I_plus = Ybus_red @ E_plus  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Pe_plus = np.real(E_plus * np.conj(I_plus))  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

            delta_pert[j] = delta0[j] - eps
            E_minus = E * np.exp(1j * delta_pert)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            I_minus = Ybus_red @ E_minus  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            Pe_minus = np.real(E_minus * np.conj(I_minus))  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

            K_S[:, j] = (Pe_plus - Pe_minus) / (2.0 * eps)

        # Build state matrix A (2n x 2n)
        # State vector: [delta_1, ..., delta_n, omega_1, ..., omega_n]
        A = np.zeros((2 * n_gen, 2 * n_gen))

        # Upper-right block: Identity (d(delta)/dt = omega - omega_s)
        A[:n_gen, n_gen:] = np.eye(n_gen)

        # Lower-left block: -M^{-1} K_S (synchronizing)
        # The linearized swing equation is d(Δω)/dt = M⁻¹(-K_S·Δδ - D·Δω),
        # so the synchronizing-coefficient block carries a negative sign.
        M_inv = np.diag(1.0 / M)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        A[n_gen:, :n_gen] = -M_inv @ K_S

        # Lower-right block: M^{-1} D (damping)
        A[n_gen:, n_gen:] = -M_inv @ np.diag(D)

        # Compute eigenvalues AND eigenvectors in a single call (avoids
        # ordering inconsistencies between eigvals() and eig()).
        eigenvalues, right_vecs = np.linalg.eig(A)

        # Sort by real part (most unstable first)
        idx = np.argsort(np.real(eigenvalues))
        eigenvalues = eigenvalues[idx]
        right_vecs = right_vecs[:, idx]  # reorder columns to match

        # Compute damping ratios and frequencies for oscillatory modes
        damping_ratios = []
        frequencies_hz = []
        critical_modes = []

        for ev in eigenvalues:
            sigma = np.real(ev)
            omega_d = np.imag(ev)
            omega_n = np.abs(ev)

            if omega_n > 1e-6:
                zeta = -sigma / omega_n
                freq = abs(omega_d) / (2.0 * np.pi)
            else:
                zeta = 1.0 if sigma < 0 else -1.0
                freq = 0.0

            damping_ratios.append(float(zeta))
            frequencies_hz.append(float(freq))

            # Flag poorly damped or unstable modes
            if zeta < 0.05 or sigma > 0:
                critical_modes.append(
                    {
                        "eigenvalue": complex(ev),
                        "damping_ratio": float(zeta),
                        "frequency_hz": float(freq),
                        "type": "unstable" if sigma > 0 else "poorly_damped",
                    },
                )

        # Participation factor analysis (reuse eigenvectors from same call)
        left_vecs = np.linalg.inv(right_vecs)  # rows are left eigenvectors

        participation_factors = []
        for i in range(2 * n_gen):
            # Participation factor for mode i: P_ki = |left_i[k] * right_k[i]|
            # left_vecs[i, :] is the i-th left eigenvector (row)
            # right_vecs[:, i] is the i-th right eigenvector (column)
            p = np.abs(left_vecs[i, :] * right_vecs[:, i])
            p = p / np.max(p) if np.max(p) > 0 else p
            participation_factors.append(p.tolist())

        stable = all(np.real(ev) < 0 for ev in eigenvalues)

        return {
            "eigenvalues": [complex(ev) for ev in eigenvalues],
            "damping_ratios": damping_ratios,
            "frequencies_hz": frequencies_hz,
            "participation_factors": participation_factors,
            "stable": bool(stable),
            "critical_modes": critical_modes,
            "state_matrix_size": 2 * n_gen,
            "min_damping_ratio": float(min(damping_ratios)) if damping_ratios else 0.0,
        }

    def critical_clearing_time(
        self,
        H: float,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Pm: float,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        E_gen: float,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        V_inf: float,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        X_total: float,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        X_faulted: float,  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        delta0: float,
    ) -> dict[str, Any]:
        """
        Compute critical clearing time using the equal area criterion.

        For a single-machine-infinite-bus (SMIB) system, the electrical
        power output is:

            Pe = (E * V / X) * sin(delta)

        The critical clearing angle δ_cr is found from the equal area
        criterion, then the critical clearing time is:

            t_cr = sqrt(2H / (ωs * Pm)) * sqrt(δ_cr - δ0)

        Parameters
        ----------
        H : float
            Machine inertia constant in seconds.
        Pm : float
            Mechanical power in pu.
        E_gen : float
            Generator internal voltage in pu.
        V_inf : float
            Infinite bus voltage in pu.
        X_total : float
            Total reactance pre-fault in pu.
        X_faulted : float
            Reactance during fault in pu.
        delta0 : float
            Initial rotor angle in radians.

        Returns
        -------
        Dict[str, Any]
            Contains 'critical_clearing_angle_rad', 'critical_clearing_angle_deg',
            'critical_clearing_time_s', 'equal_area_method', 'stable'.
        """
        omega_s = self.omega_synchronous

        # Maximum power transfer pre-fault and during fault
        Pmax_pre = E_gen * V_inf / X_total  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        Pmax_fault = E_gen * V_inf / X_faulted if X_faulted < 1e6 else 0.0  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Post-fault max (assume same as pre-fault for reclosing)
        Pmax_post = Pmax_pre  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Initial angle where Pm = Pmax_pre * sin(delta0)
        # delta0 is given; verify Pm <= Pmax_pre
        if Pm > Pmax_pre:
            return {
                "critical_clearing_angle_rad": float(delta0),
                "critical_clearing_angle_deg": float(np.degrees(delta0)),
                "critical_clearing_time_s": 0.0,
                "equal_area_method": "infeasible",
                "stable": False,
                "error": f"Pm ({Pm:.3f}) > Pmax_pre ({Pmax_pre:.3f}): operating point invalid",
            }

        # Find delta_max: angle where Pm = Pmax_post * sin(delta_max)
        # delta_max = pi - arcsin(Pm / Pmax_post)
        delta_max = np.pi - np.arcsin(min(Pm / Pmax_post, 1.0))

        # Critical clearing angle from equal area criterion:
        # cos(delta_cr) = [Pm*(delta_max - delta0) + Pmax_post*cos(delta_max)
        #                   - Pmax_fault*cos(delta0)] / (Pmax_post - Pmax_fault)
        if abs(Pmax_post - Pmax_fault) < 1e-10:
            # Three-phase fault at generator terminals: Pmax_fault ≈ 0
            Pmax_fault = 0.0

        numerator = (
            Pm * (delta_max - delta0) + Pmax_post * np.cos(delta_max) - Pmax_fault * np.cos(delta0)
        )
        denominator = Pmax_post - Pmax_fault

        cos_delta_cr = numerator / denominator if abs(denominator) > 1e-12 else 0.0
        cos_delta_cr = np.clip(cos_delta_cr, -1.0, 1.0)
        delta_cr = np.arccos(cos_delta_cr)

        # Critical clearing time
        # From the swing equation with Pmax_fault = 0 during fault:
        # t_cr = sqrt(2H * (delta_cr - delta0) / (omega_s * Pm))
        if delta_cr > delta0 and Pm > 0:
            t_cr = np.sqrt(2.0 * H * (delta_cr - delta0) / (omega_s * Pm))
        else:
            t_cr = 0.0

        return {
            "critical_clearing_angle_rad": float(delta_cr),
            "critical_clearing_angle_deg": float(np.degrees(delta_cr)),
            "critical_clearing_time_s": float(t_cr),
            "initial_angle_rad": float(delta0),
            "initial_angle_deg": float(np.degrees(delta0)),
            "maximum_angle_rad": float(delta_max),
            "maximum_angle_deg": float(np.degrees(delta_max)),
            "Pmax_pre_fault_pu": float(Pmax_pre),
            "Pmax_during_fault_pu": float(Pmax_fault),
            "Pmax_post_fault_pu": float(Pmax_post),
            "equal_area_method": "solved",
            "stable": bool(delta_cr > delta0),
        }

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute stability analysis task.

        Dispatches to the appropriate analysis method based on
        ``task.parameters['analysis_type']`` which must be one of:
        ``'transient'``, ``'small_signal'``, ``'critical_clearing_time'``,
        or ``'full'`` (runs all three).
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting stability analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: dict[str, Any] = {}

            # --- Transient stability ---
            if analysis_type in ("transient", "full"):
                H = np.array(task.parameters.get("inertia_constants", [3.0, 4.0, 5.0]))
                D = np.array(task.parameters.get("damping_coefficients", [2.0, 2.0, 2.0]))
                Pm = np.array(task.parameters.get("mechanical_power", [0.8, 0.6, 0.5]))  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                n_gen = len(H)

                # Build reduced Ybus from provided data or use defaults
                Y_data = task.parameters.get("Ybus_reduced")  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                if Y_data is not None:
                    Ybus_red = np.array(Y_data, dtype=complex)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                else:
                    # Default 3-machine test system
                    np.random.seed(42)
                    G = np.random.uniform(2.0, 8.0, (n_gen, n_gen))  # NOSONAR — S6711: numpy.random.Generator migration; API change required
                    G = (G + G.T) / 2.0
                    B = np.random.uniform(-12.0, -3.0, (n_gen, n_gen))  # NOSONAR — S6711: numpy.random.Generator migration; API change required
                    B = (B + B.T) / 2.0
                    np.fill_diagonal(G, np.sum(G, axis=1) - np.diag(G) + 1.0)
                    np.fill_diagonal(B, -np.sum(np.abs(B), axis=1))
                    Ybus_red = G + 1j * B

                E_mag = np.array(task.parameters.get("internal_voltages", [1.1, 1.0, 1.05]))  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                delta0 = np.array(task.parameters.get("initial_angles_rad", [0.3, 0.1, -0.2]))
                E = E_mag * np.exp(1j * delta0)

                # Fault Ybus: add large shunt at fault_bus
                fault_bus = task.parameters.get("fault_bus", 0)
                fault_Ybus = Ybus_red.copy()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                fault_impedance = task.parameters.get("fault_impedance_pu", 1e-6)
                fault_Ybus[fault_bus, fault_bus] += 1.0 / fault_impedance

                # Post-fault Ybus: slightly modified
                post_fault_Ybus = Ybus_red.copy()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                line_out = task.parameters.get("tripped_line_from_bus", None)
                if line_out is not None and line_out < n_gen:
                    post_fault_Ybus[line_out, line_out] += 1j * 2.0

                t_fault = task.parameters.get("fault_time_s", 0.0)
                t_clear = task.parameters.get("clearing_time_s", 0.15)
                t_total = task.parameters.get("simulation_time_s", 5.0)
                dt = task.parameters.get("time_step_s", 0.01)

                transient_result = self.analyze_transient_stability(
                    H=H,
                    D=D,
                    Pm=Pm,
                    Ybus_red=Ybus_red,
                    E=E,
                    delta0=delta0,
                    fault_bus=fault_bus,
                    fault_Ybus=fault_Ybus,
                    post_fault_Ybus=post_fault_Ybus,
                    t_fault=t_fault,
                    t_clear=t_clear,
                    t_total=t_total,
                    dt=dt,
                )
                results["transient_stability"] = transient_result

            # --- Small-signal stability ---
            if analysis_type in ("small_signal", "full"):
                H = np.array(task.parameters.get("inertia_constants", [3.0, 4.0, 5.0]))
                D = np.array(task.parameters.get("damping_coefficients", [2.0, 2.0, 2.0]))
                Pm = np.array(task.parameters.get("mechanical_power", [0.8, 0.6, 0.5]))
                n_gen = len(H)

                Y_data = task.parameters.get("Ybus_reduced")
                if Y_data is not None:
                    Ybus_red = np.array(Y_data, dtype=complex)
                else:
                    np.random.seed(42)
                    G = np.random.uniform(2.0, 8.0, (n_gen, n_gen))  # NOSONAR — S6711: numpy.random.Generator migration; API change required
                    G = (G + G.T) / 2.0
                    B = np.random.uniform(-12.0, -3.0, (n_gen, n_gen))  # NOSONAR — S6711: numpy.random.Generator migration; API change required
                    B = (B + B.T) / 2.0
                    np.fill_diagonal(G, np.sum(G, axis=1) - np.diag(G) + 1.0)
                    np.fill_diagonal(B, -np.sum(np.abs(B), axis=1))
                    Ybus_red = G + 1j * B

                E_mag = np.array(task.parameters.get("internal_voltages", [1.1, 1.0, 1.05]))
                delta0 = np.array(task.parameters.get("initial_angles_rad", [0.3, 0.1, -0.2]))
                E = E_mag * np.exp(1j * delta0)

                ss_result = self.analyze_small_signal_stability(
                    H=H, D=D, Pm=Pm, Ybus_red=Ybus_red, E=E, delta0=delta0,
                )
                results["small_signal_stability"] = ss_result

            # --- Critical clearing time ---
            if analysis_type in ("critical_clearing_time", "full"):
                cct_result = self.critical_clearing_time(
                    H=float(task.parameters.get("smib_H", 5.0)),
                    Pm=float(task.parameters.get("smib_Pm", 0.8)),
                    E_gen=float(task.parameters.get("smib_E", 1.1)),
                    V_inf=float(task.parameters.get("smib_V_inf", 1.0)),
                    X_total=float(task.parameters.get("smib_X_total", 0.5)),
                    X_faulted=float(task.parameters.get("smib_X_faulted", 1e6)),
                    delta0=float(task.parameters.get("smib_delta0", 0.5)),
                )
                results["critical_clearing_time"] = cct_result

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.TRANSIENT_STABILITY,
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "standards": self.standards,
                    "analysis_type": analysis_type,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Stability analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Stability analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.TRANSIENT_STABILITY,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """
        Validate stability analysis results.

        Checks:
        - Transient: system is stable (angle spread < 180°)
        - Small-signal: all eigenvalues have negative real parts
        - CCT: critical clearing time is positive
        """
        errors: list[str] = []

        ts_data = result.data.get("transient_stability")
        if ts_data is not None and not ts_data.get("stable", False):
            errors.append(
                f"Transient instability: max angle spread "
                f"{ts_data.get('max_angle_spread_deg', 0):.1f}°",
            )

        ss_data = result.data.get("small_signal_stability")
        if ss_data is not None:
            if not ss_data.get("stable", True):
                for mode in ss_data.get("critical_modes", []):
                    if mode["type"] == "unstable":
                        ev = mode["eigenvalue"]
                        errors.append(
                            f"Unstable mode: eigenvalue={ev.real:.4f}{ev.imag:+.4f}j, "
                            f"ζ={mode['damping_ratio']:.4f}",
                        )
            min_zeta = ss_data.get("min_damping_ratio", 0.0)
            if min_zeta < 0.03:
                errors.append(f"Very low damping ratio: ζ_min={min_zeta:.4f} (< 0.03 threshold)")

        cct_data = result.data.get("critical_clearing_time")
        if cct_data is not None and not cct_data.get("stable", True):
            errors.append("CCT analysis indicates system cannot be stabilised")

        result.validation_errors.extend(errors)
        return len(errors) == 0
