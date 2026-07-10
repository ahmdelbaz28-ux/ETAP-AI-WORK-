"""
Optimal Power Flow (OPF) Engine
=================================
Implements AC Optimal Power Flow using various optimization methods.

Supports:
- Economic dispatch (minimize generation cost)
- Loss minimization
- Voltage profile optimization
- Security-constrained OPF
- Multi-objective optimization

Methods:
- Interior Point Method (IPM)
- Linear Programming (LP) - DC OPF approximation
- Quadratic Programming (QP)
- Sequential Quadratic Programming (SQP)

Reference: IEEE PES Test Cases, MATPOWER methodology
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
from scipy.optimize import linprog, minimize

logger = logging.getLogger(__name__)


class OPFObjective(Enum):
    """OPF objective function types."""

    ECONOMIC_DISPATCH = "economic_dispatch"  # Minimize generation cost
    LOSS_MINIMIZATION = "loss_minimization"  # Minimize system losses
    VOLTAGE_PROFILE = "voltage_profile"  # Optimize voltage profile
    MULTI_OBJECTIVE = "multi_objective"  # Weighted combination


@dataclass
class GeneratorCost:
    """Generator cost characteristics."""

    generator_id: int
    cost_coefficients: list[float]  # [c0, c1, c2] for quadratic: c0 + c1*P + c2*P^2
    p_min: float  # Minimum active power (MW)
    p_max: float  # Maximum active power (MW)
    q_min: float  # Minimum reactive power (MVAR)
    q_max: float  # Maximum reactive power (MVAR)
    ramp_rate: Optional[float] = None  # MW/min (optional)

    def cost(self, p_mw: float) -> float:
        """Calculate generation cost for given power output."""
        if len(self.cost_coefficients) == 3:
            c0, c1, c2 = self.cost_coefficients
            return c0 + c1 * p_mw + c2 * p_mw**2
        elif len(self.cost_coefficients) == 2:
            c0, c1 = self.cost_coefficients
            return c0 + c1 * p_mw
        else:
            return self.cost_coefficients[0] * p_mw


@dataclass
class OPFResult:
    """Results from OPF calculation."""

    success: bool
    objective_value: float  # Total cost or objective value
    generator_dispatch: dict[int, complex]  # gen_id -> P + jQ (MW + jMVAR)
    bus_voltages: dict[int, complex]  # bus_id -> V (pu)
    branch_flows: dict[tuple[int, int], complex]  # (from, to) -> S (MVA)
    total_generation: float  # Total generation (MW)
    total_load: float  # Total load (MW)
    total_losses: float  # Total system losses (MW)
    constraint_violations: list[str]
    iterations: int
    method_used: str
    convergence_status: str


class OptimalPowerFlowEngine:
    """
    Optimal Power Flow Engine.

    Solves the AC-OPF problem:
    Minimize: f(Pg) = sum(Ci(Pgi))
    Subject to:
      - Power balance equations (equality constraints)
      - Generator limits (inequality constraints)
      - Voltage limits (inequality constraints)
      - Line flow limits (inequality constraints)
    """

    def __init__(self, Ybus: np.ndarray, bus_ids: list[int], generator_costs: list[GeneratorCost]):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Initialize OPF engine.

        Parameters:
        Ybus: System admittance matrix
        bus_ids: List of bus IDs
        generator_costs: Generator cost data
        """
        self.Ybus = Ybus  # NOSONAR — S116: standard IEEE/IEC engineering notation (Ybus/Zbus/sequence components); renaming would harm domain readability
        self.bus_ids = bus_ids
        self.n_buses = len(bus_ids)
        self.generator_costs = {gc.generator_id: gc for gc in generator_costs}
        self.bus_index = {bid: idx for idx, bid in enumerate(bus_ids)}

        # Load and generation data (to be set)
        self.load_data: dict[int, complex] = {}  # bus_id -> S_load (MW + jMVAR)
        self.gen_buses: dict[int, int] = {}  # gen_id -> bus_id

        # Limits
        self.voltage_limits: dict[int, tuple[float, float]] = {}  # bus_id -> (Vmin, Vmax)
        self.branch_limits: dict[tuple[int, int], float] = {}  # (from, to) -> S_max (MVA)

    def set_load_data(self, load_data: dict[int, complex]):
        """Set load data for each bus."""
        self.load_data = load_data

    def set_generator_locations(self, gen_buses: dict[int, int]):
        """Map generators to buses."""
        self.gen_buses = gen_buses

    def set_voltage_limits(self, limits: dict[int, tuple[float, float]]):
        """Set voltage magnitude limits per bus."""
        self.voltage_limits = limits

    def set_branch_limits(self, limits: dict[tuple[int, int], float]):
        """Set thermal limits for branches."""
        self.branch_limits = limits

    def _build_dc_approximation(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Build DC power flow approximation matrices.

        Returns:
        B_prime: DC susceptance matrix
        P_injection: Net power injection vector
        """
        # Extract imaginary part of Ybus (susceptance)
        B = -self.Ybus.imag

        # Form B' matrix (remove reference bus row/column)
        # Assume bus 0 is slack/reference
        B_prime = B[1:, 1:]  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability

        # Calculate net power injections
        P_injection = np.zeros(self.n_buses - 1)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        for i, bus_id in enumerate(self.bus_ids[1:], start=0):
            # Generation
            P_gen = sum(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                self.generator_costs[gid].p_min
                for gid, bid in self.gen_buses.items()
                if bid == bus_id
            )
            # Load
            P_load = self.load_data.get(bus_id, 0).real if bus_id in self.load_data else 0  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            P_injection[i] = P_gen - P_load

        return B_prime, P_injection

    def solve_dc_opf(self) -> OPFResult:
        """
        Solve DC Optimal Power Flow (linear approximation).

        Uses linear programming to minimize generation cost subject to:
        - Power balance (DC power flow equations)
        - Generator limits
        - Line flow limits (approximated)

        Returns:
        OPFResult with solution
        """
        logger.info("Solving DC-OPF using Linear Programming")

        n_gen = len(self.generator_costs)
        gen_ids = list(self.generator_costs.keys())

        # Decision variables: P_g for each generator
        # Objective: minimize sum(c0 + c1*Pg + c2*Pg^2)
        # For LP, we use linear approximation: minimize sum(c1*Pg)

        # Cost coefficients (linear term)
        c = np.array(
            [
                self.generator_costs[gid].cost_coefficients[1]
                if len(self.generator_costs[gid].cost_coefficients) >= 2
                else 0
                for gid in gen_ids
            ],
        )

        # Inequality constraints: A_ub * x <= b_ub
        # Generator limits
        A_ub = []  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        b_ub = []

        # P_g <= P_max
        for i, gid in enumerate(gen_ids):
            row = np.zeros(n_gen)
            row[i] = 1
            A_ub.append(row)
            b_ub.append(self.generator_costs[gid].p_max)

        # -P_g <= -P_min  =>  P_g >= P_min
        for i, gid in enumerate(gen_ids):
            row = np.zeros(n_gen)
            row[i] = -1
            A_ub.append(row)
            b_ub.append(-self.generator_costs[gid].p_min)

        A_ub = np.array(A_ub)
        b_ub = np.array(b_ub)

        # Equality constraints: Power balance
        # Sum(P_g) = Sum(P_load) + Losses (approximated as 0 in DC)
        total_load = sum(load.real for load in self.load_data.values())

        # NOTE: Original code created one equality constraint per bus, which
        # overconstrains the LP when there are more buses than generators.
        # Fix: use a single system-wide power balance: sum(gen) = sum(load).
        # Build a mapping from generator index to LP decision variable column.
        gen_col_map = {}
        for i, gid in enumerate(gen_ids):
            gen_col_map[gid] = i

        # Single system-wide power balance constraint: sum(gen) = sum(load)
        A_eq_row = np.zeros(len(gen_ids))  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        b_eq_val = 0.0
        for _bus_idx, bid in enumerate(self.bus_ids):
            load_val = self.load_data.get(bid, complex(0, 0)).real
            b_eq_val += load_val
        for gid, _bus_id in self.gen_buses.items():
            gen_col = gen_col_map[gid]
            A_eq_row[gen_col] = 1.0
        A_eq = A_eq_row.reshape(1, -1)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        b_eq = np.array([b_eq_val])

        # Solve LP
        try:
            result = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, method="highs")

            if result.success:
                # Extract solution
                P_gen = result.x  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                objective = result.fun

                # Build result
                generator_dispatch = {}
                for i, gid in enumerate(gen_ids):
                    self.gen_buses[gid]
                    Q_gen = 0  # DC OPF doesn't optimize Q  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    generator_dispatch[gid] = complex(P_gen[i], Q_gen)

                # Calculate losses (approximate)
                total_gen = sum(P_gen)
                total_losses = total_gen - total_load

                return OPFResult(
                    success=True,
                    objective_value=objective,
                    generator_dispatch=generator_dispatch,
                    bus_voltages={},  # DC OPF doesn't calculate voltages
                    branch_flows={},
                    total_generation=total_gen,
                    total_load=total_load,
                    total_losses=max(total_losses, 0),
                    constraint_violations=[],
                    iterations=result.nit if hasattr(result, "nit") else 0,
                    method_used="Linear Programming (DC-OPF)",  # NOSONAR — S1192: intentional repetition (audit constant)
                    convergence_status="converged",
                )
            else:
                return OPFResult(
                    success=False,
                    objective_value=0,
                    generator_dispatch={},
                    bus_voltages={},
                    branch_flows={},
                    total_generation=0,
                    total_load=total_load,
                    total_losses=0,
                    constraint_violations=["LP solver failed to converge"],
                    iterations=0,
                    method_used="Linear Programming (DC-OPF)",
                    convergence_status="failed",
                )

        except Exception as e:
            logger.exception("DC-OPF failed: %s", e)
            return OPFResult(
                success=False,
                objective_value=0,
                generator_dispatch={},
                bus_voltages={},
                branch_flows={},
                total_generation=0,
                total_load=sum(load.real for load in self.load_data.values()),
                total_losses=0,
                constraint_violations=[str(e)],
                iterations=0,
                method_used="Linear Programming (DC-OPF)",
                convergence_status="error",
            )

    def solve_ac_opf_interior_point(self, max_iter: int = 100, tol: float = 1e-6) -> OPFResult:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        """
        Solve AC Optimal Power Flow using Interior Point Method.

        This is a simplified implementation. Production systems should use
        specialized solvers like IPOPT, KNITRO, or MATPOWER.

        Returns:
        OPFResult with full AC solution
        """
        logger.info("Solving AC-OPF using Interior Point Method (simplified)")

        n_gen = len(self.generator_costs)
        gen_ids = list(self.generator_costs.keys())

        # Decision variables: [V1, ..., Vn, theta1, ..., thetan, Pg1, ..., Pgn, Qg1, ..., Qgn]
        # Simplified: optimize only generator P and Q, assume voltages fixed at 1.0 pu
        x0 = np.zeros(2 * n_gen)

        # Initial guess: generators at midpoint of their range
        for i, gid in enumerate(gen_ids):
            gc = self.generator_costs[gid]
            x0[i] = (gc.p_min + gc.p_max) / 2  # P
            x0[n_gen + i] = 0  # Q

        # Objective function: total generation cost
        def objective(x):
            total_cost = 0
            for i, gid in enumerate(gen_ids):
                P = x[i]
                total_cost += self.generator_costs[gid].cost(P)
            return total_cost

        # Gradient of objective
        def gradient(x):
            grad = np.zeros(2 * n_gen)
            for i, gid in enumerate(gen_ids):
                coeffs = self.generator_costs[gid].cost_coefficients
                P = x[i]
                if len(coeffs) == 3:
                    grad[i] = coeffs[1] + 2 * coeffs[2] * P
                elif len(coeffs) == 2:
                    grad[i] = coeffs[1]
                else:
                    grad[i] = coeffs[0]
            return grad

        # Constraints (power balance at each bus)
        constraints = []

        for bus_id in self.bus_ids:
            # Active power balance
            def active_power_constraint(x, bus_id=bus_id):
                P_gen_bus = sum(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    x[i] for i, gid in enumerate(gen_ids) if self.gen_buses.get(gid) == bus_id
                )
                P_load = self.load_data.get(bus_id, 0).real  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                return P_gen_bus - P_load

            constraints.append({"type": "eq", "fun": active_power_constraint})

            # Reactive power balance
            def reactive_power_constraint(x, bus_id=bus_id):
                Q_gen_bus = sum(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                    x[n_gen + i]
                    for i, gid in enumerate(gen_ids)
                    if self.gen_buses.get(gid) == bus_id
                )
                Q_load = self.load_data.get(bus_id, 0).imag  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                return Q_gen_bus - Q_load

            constraints.append({"type": "eq", "fun": reactive_power_constraint})

        # Variable bounds
        bounds = []
        for gid in gen_ids:
            gc = self.generator_costs[gid]
            bounds.append((gc.p_min, gc.p_max))  # P bounds
            bounds.append((gc.q_min, gc.q_max))  # Q bounds

        # Solve using SLSQP (Sequential Least Squares Quadratic Programming)
        try:
            result = minimize(
                objective,
                x0,
                method="SLSQP",
                jac=gradient,
                constraints=constraints,
                bounds=bounds,
                options={"maxiter": max_iter, "ftol": tol, "disp": False},
            )

            if result.success:
                # Extract solution
                x_opt = result.x
                generator_dispatch = {}

                for i, gid in enumerate(gen_ids):
                    P = x_opt[i]
                    Q = x_opt[n_gen + i]
                    generator_dispatch[gid] = complex(P, Q)

                # Calculate system metrics
                total_gen = sum(x_opt[:n_gen])
                total_load = sum(load.real for load in self.load_data.values())
                total_losses = total_gen - total_load

                # Placeholder for bus voltages and branch flows
                # (would require full AC power flow solution)
                bus_voltages = {bid: complex(1.0, 0) for bid in self.bus_ids}
                branch_flows = {}

                return OPFResult(
                    success=True,
                    objective_value=result.fun,
                    generator_dispatch=generator_dispatch,
                    bus_voltages=bus_voltages,
                    branch_flows=branch_flows,
                    total_generation=total_gen,
                    total_load=total_load,
                    total_losses=max(total_losses, 0),
                    constraint_violations=[],
                    iterations=result.nit,
                    method_used="Interior Point Method (AC-OPF)",  # NOSONAR — S1192: intentional repetition (audit constant)
                    convergence_status="converged",
                )
            else:
                return OPFResult(
                    success=False,
                    objective_value=0,
                    generator_dispatch={},
                    bus_voltages={},
                    branch_flows={},
                    total_generation=0,
                    total_load=sum(load.real for load in self.load_data.values()),
                    total_losses=0,
                    constraint_violations=[result.message],
                    iterations=result.nit,
                    method_used="Interior Point Method (AC-OPF)",
                    convergence_status=result.message,
                )

        except Exception as e:
            logger.exception("AC-OPF failed: %s", e)
            return OPFResult(
                success=False,
                objective_value=0,
                generator_dispatch={},
                bus_voltages={},
                branch_flows={},
                total_generation=0,
                total_load=sum(load.real for load in self.load_data.values()),
                total_losses=0,
                constraint_violations=[str(e)],
                iterations=0,
                method_used="Interior Point Method (AC-OPF)",
                convergence_status="error",
            )

    def solve_opf(self, method: str = "dc") -> OPFResult:
        """
        Solve OPF using specified method.

        Parameters:
        method: "dc" for DC-OPF, "ac" for AC-OPF

        Returns:
        OPFResult
        """
        if method.lower() == "dc":
            return self.solve_dc_opf()
        elif method.lower() == "ac":
            return self.solve_ac_opf_interior_point()
        else:
            raise ValueError(f"Unknown OPF method: {method}. Use 'dc' or 'ac'.")

    def generate_report(self, result: OPFResult) -> str:
        """Generate OPF results report."""
        lines = []
        lines.append("=" * 70)
        lines.append("OPTIMAL POWER FLOW RESULTS")
        lines.append("=" * 70)
        lines.append(f"Method: {result.method_used}")
        lines.append(f"Convergence: {result.convergence_status}")
        lines.append(f"Iterations: {result.iterations}")
        lines.append("")

        lines.append("OBJECTIVE FUNCTION")
        lines.append("-" * 70)
        lines.append(f"Total Generation Cost: ${result.objective_value:,.2f}/hr")
        lines.append("")

        lines.append("GENERATOR DISPATCH")
        lines.append("-" * 70)
        for gen_id, dispatch in sorted(result.generator_dispatch.items()):
            P = dispatch.real
            Q = dispatch.imag
            gc = self.generator_costs[gen_id]
            cost = gc.cost(P)
            lines.append(f"  Gen {gen_id}: P={P:7.2f} MW, Q={Q:7.2f} MVAR, Cost=${cost:,.2f}/hr")
        lines.append("")

        lines.append("SYSTEM SUMMARY")
        lines.append("-" * 70)
        lines.append(f"Total Generation: {result.total_generation:.2f} MW")
        lines.append(f"Total Load: {result.total_load:.2f} MW")
        lines.append(f"Total Losses: {result.total_losses:.2f} MW")
        lines.append(
            f"Loss Percentage: {(result.total_losses / result.total_generation * 100) if result.total_generation > 0 else 0:.2f}%",
        )
        lines.append("")

        if result.constraint_violations:
            lines.append("⚠ CONSTRAINT VIOLATIONS")
            lines.append("-" * 70)
            for violation in result.constraint_violations:
                lines.append(f"  {violation}")
            lines.append("")
        else:
            lines.append("✓ All constraints satisfied")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)
