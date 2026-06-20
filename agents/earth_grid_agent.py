"""
AhmedETAP - Earth Grid Design Agent
=======================================================
Substation ground grid design and safety verification per IEEE 80.

Capabilities:
- Ground grid design (mesh voltage, step voltage, touch voltage)
- Soil resistivity analysis (two-layer model)
- Safety verification against allowable body current limits
- Grid configuration optimization

Standards:
- IEEE 80-2013: Guide for Safety in AC Substation Grounding
- IEEE 81: Guide for Measuring Earth Resistivity
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class EarthGridAgent(BaseAgent):
    """
    Earth Grid Design and Safety Verification Agent (IEEE 80).

    Implements the IEEE 80 methodology for substation grounding design,
    including:

    - Mesh voltage calculation (worst-case touch voltage within the grid)
    - Step voltage calculation (worst-case voltage across a person's stride)
    - Touch voltage calculation (hand-to-feet voltage at grid perimeter)
    - Allowable voltage limits based on body weight and fault duration
    - Soil resistivity analysis with two-layer model support
    - Safety verification against IEEE 80 criteria

    Key formulas (IEEE 80-2013):

    Allowable touch voltage:
        E_touch = (1000 + 1.5 ρ_s C_s) × 0.157 / √t_s

    Allowable step voltage:
        E_step = (1000 + 6.0 ρ_s C_s) × 0.157 / √t_s

    where ρ_s is surface layer resistivity, C_s is the surface layer
    derating factor, and t_s is the shock duration in seconds.
    """

    prompt_handle = "earth_grid_agent"

    def __init__(self) -> None:
        super().__init__("EarthGridAgent")
        self.standards = ["IEEE 80-2013", "IEEE 81-2012"]

    # ------------------------------------------------------------------
    # Surface layer derating factor
    # ------------------------------------------------------------------

    @staticmethod
    def _surface_derating_factor(
        rho_s: float, rho_b: float, hs: float
    ) -> float:
        """
        Compute surface layer derating factor C_s per IEEE 80 Eq. 27.

        Parameters
        ----------
        rho_s : float
            Surface layer resistivity (Ω·m).
        rho_b : float
            Bottom (native soil) resistivity (Ω·m).
        hs : float
            Surface layer thickness (m).

        Returns
        -------
        float
            Derating factor C_s (0 < C_s ≤ 1).
        """
        K = (rho_s - rho_b) / (rho_s + rho_b)
        # IEEE 80 Eq. 27:
        Cs = 1.0 - ((1.0 - 0.09) / (2.0 * hs + 0.09)) * (1.0 - K)
        return float(np.clip(Cs, 0.01, 1.0))

    # ------------------------------------------------------------------
    # Allowable voltage limits
    # ------------------------------------------------------------------

    def _allowable_voltages(
        self,
        rho_s: float,
        rho_b: float,
        hs: float,
        fault_duration_s: float,
        body_weight_kg: float = 70.0,
    ) -> Dict[str, float]:
        """
        Calculate allowable touch and step voltages per IEEE 80.

        Uses the Dalziel formula with appropriate body weight factor.
        For 50 kg body weight: 0.116 / √t_s
        For 70 kg body weight: 0.157 / √t_s

        Parameters
        ----------
        rho_s : float
            Surface layer resistivity (Ω·m).
        rho_b : float
            Native soil resistivity (Ω·m).
        hs : float
            Surface layer thickness (m).
        fault_duration_s : float
            Shock/fault duration in seconds.
        body_weight_kg : float
            Body weight criterion (50 or 70 kg).

        Returns
        -------
        Dict[str, float]
            Allowable touch and step voltages in volts.
        """
        Cs = self._surface_derating_factor(rho_s, rho_b, hs)

        # Current factor based on body weight
        if body_weight_kg <= 50:
            I_body = 0.116 / np.sqrt(fault_duration_s) if fault_duration_s > 0 else float("inf")
        else:
            I_body = 0.157 / np.sqrt(fault_duration_s) if fault_duration_s > 0 else float("inf")

        # Body resistance = 1000 Ω (hand-to-feet, IEEE 80)
        R_body = 1000.0

        # Allowable touch voltage: E_touch = (R_body + 1.5 ρ_s C_s) × I_body
        E_touch = (R_body + 1.5 * rho_s * Cs) * I_body

        # Allowable step voltage: E_step = (R_body + 6.0 ρ_s C_s) × I_body
        E_step = (R_body + 6.0 * rho_s * Cs) * I_body

        return {
            "E_touch_allowable_V": float(E_touch),
            "E_step_allowable_V": float(E_step),
            "Cs_surface_derating": float(Cs),
            "body_current_A": float(I_body),
            "body_weight_kg": body_weight_kg,
        }

    # ------------------------------------------------------------------
    # Mesh voltage
    # ------------------------------------------------------------------

    def calculate_mesh_voltage(
        self,
        rho: float,
        Ig: float,
        grid_length_m: float,
        grid_width_m: float,
        n_rods: int,
        rod_length_m: float,
        conductor_diameter_m: float = 0.01,
        depth_m: float = 0.5,
        n_parallel: int = 0,
    ) -> Dict[str, Any]:
        """
        Calculate mesh voltage per IEEE 80 Section 16.5.

        The mesh voltage is the worst-case touch voltage expected within
        the grid mesh. It is calculated as:

            E_m = ρ × K_m × K_i × I_g / L_M

        where K_m is the mesh spacing factor, K_i is the irregularity
        factor, and L_M is the effective buried length.

        Parameters
        ----------
        rho : float
            Soil resistivity (Ω·m).
        Ig : float
            Maximum grid current in A.
        grid_length_m : float
            Grid length in metres.
        grid_width_m : float
            Grid width in metres.
        n_rods : int
            Number of ground rods.
        rod_length_m : float
            Length of each ground rod in metres.
        conductor_diameter_m : float
            Grid conductor diameter in metres.
        depth_m : float
            Burial depth in metres.
        n_parallel : int
            Number of parallel conductors (0 = auto-calculate).

        Returns
        -------
        Dict[str, Any]
            Mesh voltage result.
        """
        # Grid geometry
        if n_parallel <= 0:
            n_parallel = max(2, int(grid_width_m / 3.0) + 1)

        n_cross = max(2, int(grid_length_m / 3.0) + 1)

        # Spacing
        D = grid_width_m / (n_parallel - 1) if n_parallel > 1 else grid_width_m
        L_total = n_parallel * grid_length_m + n_cross * grid_width_m
        L_rods = n_rods * rod_length_m
        L_M = L_total + L_rods  # Effective buried length

        # Mesh spacing factor K_m (IEEE 80 Eq. 67)
        d = conductor_diameter_m
        h = depth_m

        K_m = (1.0 / (2.0 * np.pi)) * (
            np.log(D ** 2 / (16.0 * h * d))
            + np.log((3.0 * h + 0.4 * D) / ((2.0 * h) ** 0.5 * d))
        )

        # Irregularity factor K_i (IEEE 80 Eq. 68)
        K_i = 0.656 + 0.172 * n_parallel

        # Mesh voltage
        E_mesh = rho * K_m * K_i * Ig / L_M if L_M > 0 else 0.0

        return {
            "E_mesh_V": float(E_mesh),
            "K_m": float(K_m),
            "K_i": float(K_i),
            "L_total_conductor_m": float(L_total),
            "L_rods_m": float(L_rods),
            "L_effective_m": float(L_M),
            "n_parallel_conductors": n_parallel,
            "n_cross_conductors": n_cross,
            "mesh_spacing_D_m": float(D),
            "grid_length_m": grid_length_m,
            "grid_width_m": grid_width_m,
        }

    # ------------------------------------------------------------------
    # Step voltage
    # ------------------------------------------------------------------

    def calculate_step_voltage(
        self,
        rho: float,
        Ig: float,
        grid_length_m: float,
        grid_width_m: float,
        n_rods: int,
        rod_length_m: float,
        conductor_diameter_m: float = 0.01,
        depth_m: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Calculate step voltage per IEEE 80 Section 16.6.

        The step voltage is the worst-case voltage difference a person
        would experience when taking a 1-m stride near the grid.

            E_s = ρ × K_s × K_i × I_g / L_S

        Parameters
        ----------
        rho : float
            Soil resistivity (Ω·m).
        Ig : float
            Maximum grid current in A.
        grid_length_m, grid_width_m : float
            Grid dimensions in metres.
        n_rods : int
            Number of ground rods.
        rod_length_m : float
            Rod length in metres.
        conductor_diameter_m : float
            Conductor diameter in metres.
        depth_m : float
            Burial depth in metres.

        Returns
        -------
        Dict[str, Any]
            Step voltage result.
        """
        n_parallel = max(2, int(grid_width_m / 3.0) + 1)
        n_cross = max(2, int(grid_length_m / 3.0) + 1)
        D = grid_width_m / (n_parallel - 1) if n_parallel > 1 else grid_width_m
        h = depth_m

        L_total = n_parallel * grid_length_m + n_cross * grid_width_m
        L_rods = n_rods * rod_length_m
        L_S = 0.75 * L_total + L_rods  # Effective length for step voltage

        # Step voltage geometric factor K_s (IEEE 80-2013 Eq. 71)
        # K_s = (1/π) * [0.5*ln(1 + (D/(2h))^2) + h/D - sqrt(1 + (2h/D)^2) + 1]
        # Guard against division by zero when h=0 or D=0
        if h <= 0 or D <= 0:
            K_s = 0.0
        else:
            two_h_over_D = 2.0 * h / D
            K_s = (1.0 / np.pi) * (
                0.5 * np.log(1.0 + (D / (2.0 * h)) ** 2)
                + h / D
                - np.sqrt(1.0 + two_h_over_D ** 2)
                + 1.0
            )

        # Irregularity factor (same as mesh voltage)
        K_i = 0.656 + 0.172 * n_parallel

        E_step = rho * K_s * K_i * Ig / L_S if L_S > 0 else 0.0

        return {
            "E_step_V": float(E_step),
            "K_s": float(K_s),
            "K_i": float(K_i),
            "L_S_effective_m": float(L_S),
            "n_parallel_conductors": n_parallel,
        }

    # ------------------------------------------------------------------
    # Touch voltage (grid perimeter)
    # ------------------------------------------------------------------

    def calculate_touch_voltage(
        self,
        rho: float,
        Ig: float,
        grid_length_m: float,
        grid_width_m: float,
        n_rods: int,
        rod_length_m: float,
        conductor_diameter_m: float = 0.01,
        depth_m: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Calculate touch voltage at grid perimeter per IEEE 80.

        The touch voltage at the perimeter is estimated as the GPR
        minus the voltage rise over one mesh from the edge conductor.

            E_touch = GPR × (1 - E_mesh / GPR)

        where GPR = R_grid × I_g.

        Parameters
        ----------
        (Same as calculate_mesh_voltage)

        Returns
        -------
        Dict[str, Any]
            Touch voltage at perimeter and GPR.
        """
        # Grid resistance (Schwarz formula, simplified)
        A_grid = grid_length_m * grid_width_m
        _perimeter = 2.0 * (grid_length_m + grid_width_m)
        L_total_buried = (2.0 * grid_length_m + 2.0 * grid_width_m) + n_rods * rod_length_m

        # Simplified grid resistance (Laurent formula)
        R_grid = rho * (
            1.0 / (2.0 * np.sqrt(np.pi * A_grid)) + 1.0 / L_total_buried
        ) if L_total_buried > 0 and A_grid > 0 else 0.0

        GPR = R_grid * Ig

        # Mesh voltage for reference
        mesh_result = self.calculate_mesh_voltage(
            rho=rho,
            Ig=Ig,
            grid_length_m=grid_length_m,
            grid_width_m=grid_width_m,
            n_rods=n_rods,
            rod_length_m=rod_length_m,
            conductor_diameter_m=conductor_diameter_m,
            depth_m=depth_m,
        )

        E_mesh = mesh_result["E_mesh_V"]

        # Touch voltage at perimeter ≈ GPR - E_mesh (conservative)
        E_touch_perimeter = GPR - E_mesh if GPR > E_mesh else E_mesh

        return {
            "E_touch_perimeter_V": float(E_touch_perimeter),
            "GPR_V": float(GPR),
            "R_grid_ohm": float(R_grid),
            "grid_area_m2": float(A_grid),
            "L_total_buried_m": float(L_total_buried),
            "E_mesh_V": float(E_mesh),
        }

    # ------------------------------------------------------------------
    # Full ground grid design
    # ------------------------------------------------------------------

    def design_ground_grid(
        self,
        rho: float,
        Ig: float,
        grid_length_m: float,
        grid_width_m: float,
        n_rods: int = 4,
        rod_length_m: float = 3.0,
        rho_s: float = 3000.0,
        hs: float = 0.1,
        fault_duration_s: float = 0.5,
        conductor_diameter_m: float = 0.01,
        depth_m: float = 0.5,
        body_weight_kg: float = 70.0,
    ) -> Dict[str, Any]:
        """
        Perform complete ground grid design and safety verification.

        Calculates mesh voltage, step voltage, touch voltage, allowable
        limits, and determines whether the design is safe per IEEE 80.

        Parameters
        ----------
        rho : float
            Native soil resistivity (Ω·m).
        Ig : float
            Maximum grid current in A.
        grid_length_m : float
            Grid length (m).
        grid_width_m : float
            Grid width (m).
        n_rods : int
            Number of ground rods.
        rod_length_m : float
            Length of each ground rod (m).
        rho_s : float
            Surface layer (crushed rock) resistivity (Ω·m).
        hs : float
            Surface layer thickness (m).
        fault_duration_s : float
            Fault duration (seconds).
        conductor_diameter_m : float
            Grid conductor diameter (m).
        depth_m : float
            Grid burial depth (m).
        body_weight_kg : float
            Body weight criterion (50 or 70 kg).

        Returns
        -------
        Dict[str, Any]
            Complete grid design with safety verification.
        """
        # Compute all voltages
        mesh = self.calculate_mesh_voltage(
            rho=rho, Ig=Ig, grid_length_m=grid_length_m, grid_width_m=grid_width_m,
            n_rods=n_rods, rod_length_m=rod_length_m,
            conductor_diameter_m=conductor_diameter_m, depth_m=depth_m,
        )

        step = self.calculate_step_voltage(
            rho=rho, Ig=Ig, grid_length_m=grid_length_m, grid_width_m=grid_width_m,
            n_rods=n_rods, rod_length_m=rod_length_m,
            conductor_diameter_m=conductor_diameter_m, depth_m=depth_m,
        )

        touch = self.calculate_touch_voltage(
            rho=rho, Ig=Ig, grid_length_m=grid_length_m, grid_width_m=grid_width_m,
            n_rods=n_rods, rod_length_m=rod_length_m,
            conductor_diameter_m=conductor_diameter_m, depth_m=depth_m,
        )

        # Allowable limits
        allowable = self._allowable_voltages(
            rho_s=rho_s, rho_b=rho, hs=hs,
            fault_duration_s=fault_duration_s, body_weight_kg=body_weight_kg,
        )

        # Safety checks
        E_mesh_safe = mesh["E_mesh_V"] <= allowable["E_touch_allowable_V"]
        E_step_safe = step["E_step_V"] <= allowable["E_step_allowable_V"]
        E_touch_safe = touch["E_touch_perimeter_V"] <= allowable["E_touch_allowable_V"]
        all_safe = E_mesh_safe and E_step_safe and E_touch_safe

        return {
            "mesh_voltage": mesh,
            "step_voltage": step,
            "touch_voltage": touch,
            "allowable_limits": allowable,
            "safety": {
                "E_mesh_safe": bool(E_mesh_safe),
                "E_step_safe": bool(E_step_safe),
                "E_touch_safe": bool(E_touch_safe),
                "all_safe": bool(all_safe),
                "mesh_utilization": float(mesh["E_mesh_V"] / allowable["E_touch_allowable_V"])
                    if allowable["E_touch_allowable_V"] > 0 else float("inf"),
                "step_utilization": float(step["E_step_V"] / allowable["E_step_allowable_V"])
                    if allowable["E_step_allowable_V"] > 0 else float("inf"),
            },
            "design_parameters": {
                "rho_soil_ohm_m": rho,
                "Ig_max_A": Ig,
                "grid_length_m": grid_length_m,
                "grid_width_m": grid_width_m,
                "n_rods": n_rods,
                "rod_length_m": rod_length_m,
                "rho_surface_ohm_m": rho_s,
                "hs_surface_thickness_m": hs,
                "fault_duration_s": fault_duration_s,
                "depth_m": depth_m,
            },
        }

    # ------------------------------------------------------------------
    # Soil resistivity analysis
    # ------------------------------------------------------------------

    def analyze_soil_resistivity(
        self,
        probe_spacings_m: np.ndarray,
        measured_resistances_ohm: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Analyze soil resistivity from Wenner 4-pin test data.

        Computes apparent resistivity and fits a two-layer soil model
        using a simplified least-squares approach.

        The apparent resistivity for Wenner method:
            ρ_a = 2πa × R

        where a is the probe spacing and R is the measured resistance.

        Parameters
        ----------
        probe_spacings_m : np.ndarray
            Probe spacings in metres.
        measured_resistances_ohm : np.ndarray
            Measured resistances in Ω.

        Returns
        -------
        Dict[str, Any]
            Soil resistivity analysis results.
        """
        probe_spacings_m = np.asarray(probe_spacings_m, dtype=float)
        measured_resistances_ohm = np.asarray(measured_resistances_ohm, dtype=float)

        # Apparent resistivity
        rho_apparent = 2.0 * np.pi * probe_spacings_m * measured_resistances_ohm

        # Two-layer model: ρ_a(a) ≈ ρ_1 * [1 + 2 Σ (K^n / sqrt(1 + (2nH/a)²))]
        # Simplified: use log-linear regression to estimate ρ_1, ρ_2, H
        # Fit: ln(ρ_a) = ln(ρ_1) + slope * a (approximate for trending data)

        log_rho = np.log(rho_apparent)
        log_a = np.log(probe_spacings_m)

        # Linear regression in log-log space
        A = np.vstack([np.ones_like(log_a), log_a]).T
        coeffs, residuals, _, _ = np.linalg.lstsq(A, log_rho, rcond=None)

        rho_1_est = float(np.exp(coeffs[0]))  # Estimated top layer resistivity

        # Estimate bottom layer resistivity from trend
        rho_2_est = float(rho_apparent[-1]) if len(rho_apparent) > 0 else rho_1_est

        # Estimate layer depth from inflection point
        # Simple approach: depth where resistivity changes most
        if len(rho_apparent) > 2:
            gradients = np.diff(log_rho) / np.diff(log_a)
            max_grad_idx = int(np.argmax(np.abs(gradients)))
            H_est = float(probe_spacings_m[max_grad_idx])
        else:
            H_est = float(probe_spacings_m[-1]) if len(probe_spacings_m) > 0 else 1.0

        return {
            "probe_spacings_m": probe_spacings_m.tolist(),
            "measured_resistances_ohm": measured_resistances_ohm.tolist(),
            "apparent_resistivity_ohm_m": rho_apparent.tolist(),
            "two_layer_model": {
                "rho_top_ohm_m": rho_1_est,
                "rho_bottom_ohm_m": rho_2_est,
                "layer_depth_H_m": H_est,
                "reflection_coefficient_K": float(
                    (rho_2_est - rho_1_est) / (rho_2_est + rho_1_est)
                ),
            },
            "average_resistivity_ohm_m": float(np.mean(rho_apparent)),
            "min_resistivity_ohm_m": float(np.min(rho_apparent)),
            "max_resistivity_ohm_m": float(np.max(rho_apparent)),
        }

    # ------------------------------------------------------------------
    # Safety verification
    # ------------------------------------------------------------------

    def verify_safety(
        self,
        E_mesh_V: float,
        E_step_V: float,
        E_touch_V: float,
        rho_s: float,
        rho_b: float,
        hs: float,
        fault_duration_s: float,
        body_weight_kg: float = 70.0,
    ) -> Dict[str, Any]:
        """
        Verify ground grid safety against IEEE 80 allowable limits.

        Parameters
        ----------
        E_mesh_V : float
            Calculated mesh voltage in V.
        E_step_V : float
            Calculated step voltage in V.
        E_touch_V : float
            Calculated touch voltage at perimeter in V.
        rho_s : float
            Surface layer resistivity (Ω·m).
        rho_b : float
            Native soil resistivity (Ω·m).
        hs : float
            Surface layer thickness (m).
        fault_duration_s : float
            Fault duration in seconds.
        body_weight_kg : float
            Body weight criterion.

        Returns
        -------
        Dict[str, Any]
            Safety verification result.
        """
        allowable = self._allowable_voltages(
            rho_s=rho_s, rho_b=rho_b, hs=hs,
            fault_duration_s=fault_duration_s, body_weight_kg=body_weight_kg,
        )

        E_touch_limit = allowable["E_touch_allowable_V"]
        E_step_limit = allowable["E_step_allowable_V"]

        mesh_ok = E_mesh_V <= E_touch_limit
        step_ok = E_step_V <= E_step_limit
        touch_ok = E_touch_V <= E_touch_limit

        return {
            "E_mesh_V": float(E_mesh_V),
            "E_touch_allowable_V": float(E_touch_limit),
            "E_mesh_safe": bool(mesh_ok),
            "mesh_utilization": float(E_mesh_V / E_touch_limit) if E_touch_limit > 0 else float("inf"),
            "E_step_V": float(E_step_V),
            "E_step_allowable_V": float(E_step_limit),
            "E_step_safe": bool(step_ok),
            "step_utilization": float(E_step_V / E_step_limit) if E_step_limit > 0 else float("inf"),
            "E_touch_V": float(E_touch_V),
            "E_touch_safe": bool(touch_ok),
            "touch_utilization": float(E_touch_V / E_touch_limit) if E_touch_limit > 0 else float("inf"),
            "all_safe": bool(mesh_ok and step_ok and touch_ok),
            "allowable_limits": allowable,
        }

    # ------------------------------------------------------------------
    # Agent execute
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute ground grid analysis task.

        Dispatches based on ``task.parameters['analysis_type']``:
        - ``'design'``: Full ground grid design with safety verification
        - ``'mesh_voltage'``: Mesh voltage calculation only
        - ``'step_voltage'``: Step voltage calculation only
        - ``'touch_voltage'``: Touch voltage calculation only
        - ``'soil_resistivity'``: Soil resistivity analysis
        - ``'safety_verification'``: Safety check against given voltages
        - ``'full'``: Complete analysis (default)
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting earth grid analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}
            p = task.parameters

            if analysis_type in ("design", "full"):
                results["grid_design"] = self.design_ground_grid(
                    rho=float(p.get("rho_soil", 100.0)),
                    Ig=float(p.get("Ig_max", 5000.0)),
                    grid_length_m=float(p.get("grid_length_m", 50.0)),
                    grid_width_m=float(p.get("grid_width_m", 40.0)),
                    n_rods=int(p.get("n_rods", 4)),
                    rod_length_m=float(p.get("rod_length_m", 3.0)),
                    rho_s=float(p.get("rho_surface", 3000.0)),
                    hs=float(p.get("hs_surface_m", 0.1)),
                    fault_duration_s=float(p.get("fault_duration_s", 0.5)),
                    conductor_diameter_m=float(p.get("conductor_diameter_m", 0.01)),
                    depth_m=float(p.get("depth_m", 0.5)),
                    body_weight_kg=float(p.get("body_weight_kg", 70.0)),
                )

            if analysis_type in ("mesh_voltage", "full"):
                results["mesh_voltage"] = self.calculate_mesh_voltage(
                    rho=float(p.get("rho_soil", 100.0)),
                    Ig=float(p.get("Ig_max", 5000.0)),
                    grid_length_m=float(p.get("grid_length_m", 50.0)),
                    grid_width_m=float(p.get("grid_width_m", 40.0)),
                    n_rods=int(p.get("n_rods", 4)),
                    rod_length_m=float(p.get("rod_length_m", 3.0)),
                )

            if analysis_type in ("step_voltage", "full"):
                results["step_voltage"] = self.calculate_step_voltage(
                    rho=float(p.get("rho_soil", 100.0)),
                    Ig=float(p.get("Ig_max", 5000.0)),
                    grid_length_m=float(p.get("grid_length_m", 50.0)),
                    grid_width_m=float(p.get("grid_width_m", 40.0)),
                    n_rods=int(p.get("n_rods", 4)),
                    rod_length_m=float(p.get("rod_length_m", 3.0)),
                )

            if analysis_type in ("touch_voltage", "full"):
                results["touch_voltage"] = self.calculate_touch_voltage(
                    rho=float(p.get("rho_soil", 100.0)),
                    Ig=float(p.get("Ig_max", 5000.0)),
                    grid_length_m=float(p.get("grid_length_m", 50.0)),
                    grid_width_m=float(p.get("grid_width_m", 40.0)),
                    n_rods=int(p.get("n_rods", 4)),
                    rod_length_m=float(p.get("rod_length_m", 3.0)),
                )

            if analysis_type in ("soil_resistivity",):
                spacings = np.array(p.get("probe_spacings_m", [1, 2, 5, 10, 20, 40]))
                resistances = np.array(p.get("measured_resistances_ohm", [5.0, 3.0, 1.5, 0.8, 0.4, 0.25]))
                results["soil_resistivity"] = self.analyze_soil_resistivity(spacings, resistances)

            if analysis_type in ("safety_verification", "full"):
                if "grid_design" in results:
                    gd = results["grid_design"]
                    results["safety_verification"] = self.verify_safety(
                        E_mesh_V=gd["mesh_voltage"]["E_mesh_V"],
                        E_step_V=gd["step_voltage"]["E_step_V"],
                        E_touch_V=gd["touch_voltage"]["E_touch_perimeter_V"],
                        rho_s=float(p.get("rho_surface", 3000.0)),
                        rho_b=float(p.get("rho_soil", 100.0)),
                        hs=float(p.get("hs_surface_m", 0.1)),
                        fault_duration_s=float(p.get("fault_duration_s", 0.5)),
                        body_weight_kg=float(p.get("body_weight_kg", 70.0)),
                    )
                else:
                    results["safety_verification"] = self.verify_safety(
                        E_mesh_V=float(p.get("E_mesh_V", 500)),
                        E_step_V=float(p.get("E_step_V", 300)),
                        E_touch_V=float(p.get("E_touch_V", 800)),
                        rho_s=float(p.get("rho_surface", 3000.0)),
                        rho_b=float(p.get("rho_soil", 100.0)),
                        hs=float(p.get("hs_surface_m", 0.1)),
                        fault_duration_s=float(p.get("fault_duration_s", 0.5)),
                    )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.SHORT_CIRCUIT,  # closest available
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

            self.log_execution(f"Earth grid analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Earth grid analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.SHORT_CIRCUIT,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """Validate earth grid analysis results per IEEE 80 criteria."""
        errors: List[str] = []

        gd = result.data.get("grid_design")
        if gd is not None:
            safety = gd.get("safety", {})
            if not safety.get("all_safe", True):
                if not safety.get("E_mesh_safe", True):
                    errors.append(
                        f"Mesh voltage exceeds allowable: "
                        f"utilization={safety.get('mesh_utilization', 0):.2f}"
                    )
                if not safety.get("E_step_safe", True):
                    errors.append(
                        f"Step voltage exceeds allowable: "
                        f"utilization={safety.get('step_utilization', 0):.2f}"
                    )
                if not safety.get("E_touch_safe", True):
                    errors.append("Touch voltage at perimeter exceeds allowable limit")

        sv = result.data.get("safety_verification")
        if sv is not None and not sv.get("all_safe", True):
            errors.append("Safety verification failed: one or more voltages exceed allowable limits")

        result.validation_errors.extend(errors)
        return len(errors) == 0
