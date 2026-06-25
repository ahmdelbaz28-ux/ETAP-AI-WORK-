"""
AhmedETAP - Battery Storage Agent
=====================================================
Battery Energy Storage System (BESS) analysis per IEC 62933.

Capabilities:
- BESS sizing optimization (energy and power capacity)
- Dispatch strategy optimization (peak shaving, arbitrage, frequency regulation)
- ROI and payback period calculation
- Battery cycle life analysis (rainflow counting, degradation model)

Standards:
- IEC 62933-1: Battery energy storage systems (BESS) — Vocabulary
- IEC 62933-2-1: BESS — Common unit parameters and test methods
- IEC 62933-5-2: BESS — Safety considerations
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class BatteryStorageAgent(BaseAgent):
    """
    Battery Energy Storage System Agent (IEC 62933).

    Provides comprehensive BESS analysis including:

    - Sizing: Optimal power and energy capacity based on load profile
      and application requirements
    - Dispatch: Optimization of charge/discharge schedules for peak
      shaving, time-of-use arbitrage, and frequency regulation
    - ROI: Financial analysis with NPV, IRR, and payback period
    - Cycle life: Degradation modeling using SEI growth and rainflow
      cycle counting

    Key equations:

    Battery degradation (SEI layer growth model):
        Q_loss(t) = A × exp(Ea / RT) × t^z

    Rainflow counting for equivalent full cycles from arbitrary
    depth-of-discharge profiles.
    """

    prompt_handle = "battery_storage_agent"

    def __init__(self) -> None:
        super().__init__("BatteryStorageAgent")
        self.standards = [
            "IEC 62933-1",
            "IEC 62933-2-1",
            "IEC 62933-5-2",
        ]

    # ------------------------------------------------------------------
    # BESS sizing
    # ------------------------------------------------------------------

    def size_bess(
        self,
        load_profile_kw: np.ndarray,
        target_peak_kw: Optional[float] = None,
        max_power_kw: float = 1000.0,
        usable_soc_range: Tuple[float, float] = (0.10, 0.90),
        round_trip_efficiency: float = 0.87,
        dod_max: float = 0.90,
        discharge_duration_hours: float = 4.0,
        reserve_margin_pct: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Size BESS power and energy capacity for peak shaving.

        The power capacity is determined by the maximum load reduction
        needed, and the energy capacity by the total energy to be
        shifted.

        Parameters
        ----------
        load_profile_kw : np.ndarray
            Load profile in kW (e.g., 8760 hourly values).
        target_peak_kw : float, optional
            Target peak demand in kW. If None, set to 80th percentile.
        max_power_kw : float
            Maximum allowable BESS power in kW.
        usable_soc_range : Tuple[float, float]
            (min_soc, max_soc) operational range.
        round_trip_efficiency : float
            AC round-trip efficiency (0 to 1).
        dod_max : float
            Maximum depth of discharge (0 to 1).
        discharge_duration_hours : float
            Desired discharge duration in hours.
        reserve_margin_pct : float
            Energy reserve margin in percent.

        Returns
        -------
        Dict[str, Any]
            BESS sizing result.
        """
        load_profile_kw = np.asarray(load_profile_kw, dtype=float)

        if target_peak_kw is None:
            target_peak_kw = float(np.percentile(load_profile_kw, 80))

        # Power capacity: maximum load above target
        load_above_target = np.maximum(load_profile_kw - target_peak_kw, 0.0)
        P_required = float(np.max(load_above_target))
        P_bess = min(P_required, max_power_kw)

        # Energy capacity: total energy above target per day
        # Average daily energy to shift
        n_days = len(load_profile_kw) / 24.0
        energy_above_target = float(np.sum(load_above_target)) / n_days if n_days > 0 else 0.0

        # Account for efficiency: need more stored energy to deliver required energy
        E_deliverable = (
            energy_above_target / round_trip_efficiency
            if round_trip_efficiency > 0
            else energy_above_target
        )

        # Also consider duration-based sizing
        E_duration = P_bess * discharge_duration_hours

        # Take the larger of the two energy requirements
        E_required = max(E_deliverable, E_duration)

        # Apply SOC limits and reserve
        soc_range = usable_soc_range[1] - usable_soc_range[0]
        E_total = (
            E_required / (soc_range * (1.0 - reserve_margin_pct / 100.0))
            if soc_range > 0
            else E_required
        )

        # Energy rating at nominal conditions (accounting for DoD)
        E_nominal = E_total / dod_max if dod_max > 0 else E_total

        # Peak shaving result simulation
        shaved_profile = np.maximum(load_profile_kw - P_bess, target_peak_kw)
        # Where load is below target, BESS may charge
        _charge_available = np.maximum(target_peak_kw - load_profile_kw, 0.0)
        original_peak = float(np.max(load_profile_kw))
        new_peak = float(np.max(shaved_profile))
        peak_reduction = original_peak - new_peak
        peak_reduction_pct = (peak_reduction / original_peak * 100.0) if original_peak > 0 else 0.0

        # Storage utilization
        daily_energy_shifted = float(np.sum(load_above_target)) / n_days if n_days > 0 else 0.0
        daily_cycles = daily_energy_shifted / E_total if E_total > 0 else 0.0

        return {
            "power_capacity_kw": float(P_bess),
            "energy_capacity_kwh": float(E_total),
            "energy_nominal_kwh": float(E_nominal),
            "discharge_duration_h": float(E_total / P_bess) if P_bess > 0 else 0.0,
            "round_trip_efficiency": round_trip_efficiency,
            "usable_soc_range": list(usable_soc_range),
            "max_dod": dod_max,
            "reserve_margin_pct": reserve_margin_pct,
            "target_peak_kw": float(target_peak_kw),
            "original_peak_kw": float(original_peak),
            "new_peak_kw": float(new_peak),
            "peak_reduction_kw": float(peak_reduction),
            "peak_reduction_pct": float(peak_reduction_pct),
            "daily_energy_shifted_kwh": float(daily_energy_shifted),
            "estimated_daily_cycles": float(daily_cycles),
            "sizing_basis": "peak_shaving",
        }

    # ------------------------------------------------------------------
    # Dispatch optimization
    # ------------------------------------------------------------------

    def optimize_dispatch(
        self,
        load_profile_kw: np.ndarray,
        energy_prices: np.ndarray,
        bess_power_kw: float,
        bess_energy_kwh: float,
        round_trip_efficiency: float = 0.87,
        initial_soc: float = 0.50,
        min_soc: float = 0.10,
        max_soc: float = 0.90,
        max_daily_cycles: float = 1.5,
        strategy: str = "arbitrage",
    ) -> Dict[str, Any]:
        """
        Optimize BESS dispatch schedule.

        Implements a greedy optimization for the specified strategy:

        - **peak_shaving**: Discharge when load exceeds threshold,
          charge when load is low
        - **arbitrage**: Charge during low-price periods, discharge
          during high-price periods
        - **frequency_regulation**: Simulate regulation up/down signals

        Parameters
        ----------
        load_profile_kw : np.ndarray
            Load profile in kW.
        energy_prices : np.ndarray
            Energy price profile in $/kWh (same length as load).
        bess_power_kw : float
            BESS power rating in kW.
        bess_energy_kwh : float
            BESS energy rating in kWh.
        round_trip_efficiency : float
            AC round-trip efficiency.
        initial_soc : float
            Starting state of charge (0 to 1).
        min_soc, max_soc : float
            SOC operating limits.
        max_daily_cycles : float
            Maximum equivalent full cycles per day.
        strategy : str
            Dispatch strategy: ``'peak_shaving'``, ``'arbitrage'``,
            or ``'frequency_regulation'``.

        Returns
        -------
        Dict[str, Any]
            Optimized dispatch schedule and financial summary.
        """
        load_profile_kw = np.asarray(load_profile_kw, dtype=float)
        energy_prices = np.asarray(energy_prices, dtype=float)
        n_periods = len(load_profile_kw)

        # Initialize
        soc = np.zeros(n_periods + 1)
        soc[0] = initial_soc
        P_charge = np.zeros(n_periods)
        P_discharge = np.zeros(n_periods)
        soc_history = np.zeros(n_periods)

        sqrt_efficiency = np.sqrt(round_trip_efficiency)
        dt = 1.0  # Assume 1-hour periods
        _max_energy_throughput = max_daily_cycles * bess_energy_kwh * (n_periods / 24.0)
        cumulative_throughput = 0.0

        if strategy == "arbitrage":
            # Sort periods by price: charge at lowest, discharge at highest
            _price_ranks = np.argsort(np.argsort(energy_prices))
            n_charge = int(n_periods * 0.3)
            n_discharge = int(n_periods * 0.3)
            charge_periods = set(np.argsort(energy_prices)[:n_charge])
            discharge_periods = set(np.argsort(energy_prices)[-n_discharge:])

            for t in range(n_periods):
                current_soc = soc[t]
                available_energy = (current_soc - min_soc) * bess_energy_kwh
                available_capacity = (max_soc - current_soc) * bess_energy_kwh

                if t in discharge_periods and available_energy > 0:
                    # Discharge
                    P = min(bess_power_kw, available_energy / dt)
                    P_discharge[t] = P
                    soc[t + 1] = current_soc - (P * dt) / (bess_energy_kwh * sqrt_efficiency)
                    cumulative_throughput += P * dt

                elif t in charge_periods and available_capacity > 0:
                    # Charge
                    P = min(bess_power_kw, available_capacity / dt)
                    P_charge[t] = P
                    soc[t + 1] = current_soc + (P * dt * sqrt_efficiency) / bess_energy_kwh
                    cumulative_throughput += P * dt
                else:
                    soc[t + 1] = current_soc

                soc[t + 1] = np.clip(soc[t + 1], min_soc, max_soc)
                soc_history[t] = soc[t]

        elif strategy == "peak_shaving":
            peak_threshold = float(np.percentile(load_profile_kw, 75))

            for t in range(n_periods):
                current_soc = soc[t]
                available_energy = (current_soc - min_soc) * bess_energy_kwh
                available_capacity = (max_soc - current_soc) * bess_energy_kwh

                if load_profile_kw[t] > peak_threshold and available_energy > 0:
                    # Discharge to reduce peak
                    P = min(
                        bess_power_kw, load_profile_kw[t] - peak_threshold, available_energy / dt
                    )
                    P_discharge[t] = P
                    soc[t + 1] = current_soc - (P * dt) / (bess_energy_kwh * sqrt_efficiency)
                    cumulative_throughput += P * dt
                elif load_profile_kw[t] < peak_threshold * 0.6 and available_capacity > 0:
                    # Charge during low-load periods
                    P = min(bess_power_kw, available_capacity / dt)
                    P_charge[t] = P
                    soc[t + 1] = current_soc + (P * dt * sqrt_efficiency) / bess_energy_kwh
                    cumulative_throughput += P * dt
                else:
                    soc[t + 1] = current_soc

                # Enforce daily cycle limit
                if cumulative_throughput >= _max_energy_throughput:
                    # Stop further dispatch once cycle limit reached
                    soc[t + 1 :] = soc[t + 1]
                    soc_history[t:] = soc[t + 1]
                    break

                soc[t + 1] = np.clip(soc[t + 1], min_soc, max_soc)
                soc_history[t] = soc[t]

        elif strategy == "frequency_regulation":
            # Simulate AGC-like signal using random walk
            np.random.seed(42)
            agc_signal = np.cumsum(np.random.randn(n_periods) * 0.1)
            agc_signal = np.clip(agc_signal, -1.0, 1.0)  # Normalized

            for t in range(n_periods):
                current_soc = soc[t]
                available_energy = (current_soc - min_soc) * bess_energy_kwh
                available_capacity = (max_soc - current_soc) * bess_energy_kwh
                signal = agc_signal[t]

                if signal > 0 and available_energy > 0:
                    # Regulation up (discharge)
                    P = min(bess_power_kw * signal, available_energy / dt)
                    P_discharge[t] = P
                    soc[t + 1] = current_soc - (P * dt) / (bess_energy_kwh * sqrt_efficiency)
                    cumulative_throughput += P * dt
                elif signal < 0 and available_capacity > 0:
                    # Regulation down (charge)
                    P = min(bess_power_kw * abs(signal), available_capacity / dt)
                    P_charge[t] = P
                    soc[t + 1] = current_soc + (P * dt * sqrt_efficiency) / bess_energy_kwh
                    cumulative_throughput += P * dt
                else:
                    soc[t + 1] = current_soc

                soc[t + 1] = np.clip(soc[t + 1], min_soc, max_soc)
                soc_history[t] = soc[t]

        # Financial analysis
        revenue_discharge = np.sum(P_discharge * dt * energy_prices)
        cost_charge = np.sum(P_charge * dt * energy_prices)
        net_revenue = revenue_discharge - cost_charge

        total_charged = float(np.sum(P_charge * dt))
        total_discharged = float(np.sum(P_discharge * dt))
        equivalent_cycles = total_discharged / bess_energy_kwh if bess_energy_kwh > 0 else 0.0

        return {
            "strategy": strategy,
            "schedule": {
                "P_charge_kw": P_charge.tolist(),
                "P_discharge_kw": P_discharge.tolist(),
                "soc": soc_history.tolist(),
            },
            "financial": {
                "revenue_discharge_$": float(revenue_discharge),
                "cost_charge_$": float(cost_charge),
                "net_revenue_$": float(net_revenue),
                "daily_net_revenue_$": float(net_revenue / (n_periods / 24.0))
                if n_periods > 0
                else 0.0,
            },
            "performance": {
                "total_charged_kwh": total_charged,
                "total_discharged_kwh": total_discharged,
                "equivalent_cycles": float(equivalent_cycles),
                "average_soc": float(np.mean(soc_history)),
                "min_soc": float(np.min(soc_history)),
                "max_soc": float(np.max(soc_history)),
                "round_trip_efficiency": round_trip_efficiency,
                "actual_efficiency": float(total_discharged / total_charged)
                if total_charged > 0
                else 0.0,
            },
        }

    # ------------------------------------------------------------------
    # ROI calculation
    # ------------------------------------------------------------------

    def calculate_roi(
        self,
        bess_power_kw: float,
        bess_energy_kwh: float,
        annual_revenue_usd: float,
        capex_per_kwh: float = 300.0,
        capex_per_kw: float = 100.0,
        opex_per_kwh_year: float = 8.0,
        discount_rate: float = 0.08,
        project_life_years: int = 15,
        degradation_pct_year: float = 2.0,
        tax_rate: float = 0.21,
        itc_pct: float = 30.0,
        salvage_pct: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Calculate BESS return on investment.

        Financial metrics computed:
        - Net Present Value (NPV)
        - Internal Rate of Return (IRR)
        - Simple payback period
        - Discounted payback period
        - Levelized Cost of Storage (LCOS)

        Parameters
        ----------
        bess_power_kw : float
            BESS power capacity in kW.
        bess_energy_kwh : float
            BESS energy capacity in kWh.
        annual_revenue_usd : float
            Annual revenue from dispatch in $.
        capex_per_kwh : float
            Capital cost per kWh of storage.
        capex_per_kw : float
            Power conversion system cost per kW.
        opex_per_kwh_year : float
            Annual O&M cost per kWh.
        discount_rate : float
            Discount rate (WACC).
        project_life_years : int
            Project lifetime in years.
        degradation_pct_year : float
            Annual capacity degradation in percent.
        tax_rate : float
            Corporate tax rate.
        itc_pct : float
            Investment Tax Credit percentage.
        salvage_pct : float
            Salvage value as percentage of CAPEX.

        Returns
        -------
        Dict[str, Any]
            Financial analysis results.
        """
        # Total CAPEX
        capex_energy = bess_energy_kwh * capex_per_kwh
        capex_power = bess_power_kw * capex_per_kw
        total_capex = capex_energy + capex_power

        # ITC (Investment Tax Credit)
        itc_value = total_capex * (itc_pct / 100.0)
        net_capex = total_capex - itc_value

        # Annual cash flows
        annual_opex = bess_energy_kwh * opex_per_kwh_year
        salvage_value = total_capex * (salvage_pct / 100.0)

        cash_flows = np.zeros(project_life_years + 1)
        cash_flows[0] = -net_capex  # Year 0: investment

        for year in range(1, project_life_years + 1):
            # Revenue decreases with degradation
            degradation_factor = (1.0 - degradation_pct_year / 100.0) ** year
            revenue = annual_revenue_usd * degradation_factor
            opex = annual_opex * (1.0 + 0.02) ** (year - 1)  # 2% annual escalation

            # Taxable income
            taxable = revenue - opex - (total_capex / project_life_years)  # Depreciation
            tax = max(0, taxable * tax_rate)

            net_cash = revenue - opex - tax
            if year == project_life_years:
                net_cash += salvage_value * (1.0 - tax_rate)  # Salvage after tax

            cash_flows[year] = net_cash

        # NPV
        discount_factors = np.array(
            [(1.0 / (1.0 + discount_rate) ** t) for t in range(project_life_years + 1)]
        )
        npv = float(np.sum(cash_flows * discount_factors))

        # IRR (Newton-Raphson)
        irr = self._compute_irr(cash_flows)

        # Simple payback
        cumulative = np.cumsum(cash_flows[1:])
        payback_year = -1
        for i, c in enumerate(cumulative):
            if c >= net_capex:
                payback_year = i + 1
                break

        # Discounted payback
        discounted_cf = cash_flows[1:] * discount_factors[1:]
        cumulative_discounted = np.cumsum(discounted_cf)
        disc_payback_year = -1
        for i, c in enumerate(cumulative_discounted):
            if c >= net_capex:
                disc_payback_year = i + 1
                break

        # Levelized Cost of Storage (LCOS)
        total_discounted_energy = 0.0
        for year in range(1, project_life_years + 1):
            degradation_factor = (1.0 - degradation_pct_year / 100.0) ** year
            annual_energy = bess_energy_kwh * 365.0 * 1.0 * degradation_factor  # 1 cycle/day
            total_discounted_energy += annual_energy * discount_factors[year]

        lcos = abs(npv) / total_discounted_energy if total_discounted_energy > 0 else float("inf")

        return {
            "total_capex_$": float(total_capex),
            "capex_energy_$": float(capex_energy),
            "capex_power_$": float(capex_power),
            "itc_value_$": float(itc_value),
            "net_capex_$": float(net_capex),
            "annual_opex_$": float(annual_opex),
            "annual_revenue_usd": float(annual_revenue_usd),
            "npv_$": float(npv),
            "irr_pct": float(irr * 100.0) if irr is not None else None,
            "simple_payback_years": payback_year if payback_year > 0 else None,
            "discounted_payback_years": disc_payback_year if disc_payback_year > 0 else None,
            "lcos_$_kwh": float(lcos),
            "discount_rate_pct": float(discount_rate * 100.0),
            "project_life_years": project_life_years,
            "degradation_pct_year": degradation_pct_year,
            "salvage_value_$": float(salvage_value),
        }

    @staticmethod
    def _compute_irr(
        cash_flows: np.ndarray, max_iter: int = 100, tol: float = 1e-8
    ) -> Optional[float]:
        """Compute IRR using Newton-Raphson method."""
        x = 0.10  # Initial guess: 10%
        for _ in range(max_iter):
            npv_val = 0.0
            d_npv = 0.0
            for t, cf in enumerate(cash_flows):
                factor = (1.0 + x) ** t
                npv_val += cf / factor
                if t > 0:
                    d_npv -= t * cf / (factor * (1.0 + x))
            if abs(d_npv) < 1e-12:
                break
            x_new = x - npv_val / d_npv
            if abs(x_new - x) < tol:
                return x_new
            x = x_new
        return x if abs(npv_val) < 0.01 else None

    # ------------------------------------------------------------------
    # Cycle life analysis
    # ------------------------------------------------------------------

    def analyze_cycle_life(
        self,
        soc_profile: np.ndarray,
        battery_chemistry: str = "LFP",
        nominal_cycles: float = 6000.0,
        nominal_dod: float = 0.80,
        temperature_C: float = 25.0,
        c_rate: float = 0.25,
        calendar_life_years: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Analyze battery cycle life using rainflow counting and
        degradation modeling.

        Degradation model (SEI layer growth):
            Q_loss = A × exp(Ea / (R × T)) × N^z

        Temperature adjustment (Arrhenius):
            L(T) = L_ref × exp(Ea/R × (1/T_ref - 1/T))

        C-rate adjustment:
            L(C) = L_ref × (C_ref / C)^0.3

        Parameters
        ----------
        soc_profile : np.ndarray
            SOC time series (0 to 1).
        battery_chemistry : str
            ``'LFP'`` (LiFePO4), ``'NMC'``, or ``'LTO'``.
        nominal_cycles : float
            Cycle life at nominal DoD and conditions.
        nominal_dod : float
            Reference DoD for nominal cycle life.
        temperature_C : float
            Average operating temperature in °C.
        c_rate : float
            Average C-rate of operation.
        calendar_life_years : float
            Calendar life limit in years.

        Returns
        -------
        Dict[str, Any]
            Cycle life analysis result.
        """
        soc_profile = np.asarray(soc_profile, dtype=float)

        # Rainflow counting (simplified 4-point method)
        cycles = self._rainflow_count(soc_profile)

        # Chemistry parameters
        chemistry_params = {
            "LFP": {"Ea_kJmol": 35.0, "z": 0.5, "nominal_cycles": 6000, "knees": 0.80},
            "NMC": {"Ea_kJmol": 50.0, "z": 0.55, "nominal_cycles": 3000, "knees": 0.70},
            "LTO": {"Ea_kJmol": 25.0, "z": 0.45, "nominal_cycles": 15000, "knees": 0.85},
        }

        params = chemistry_params.get(battery_chemistry, chemistry_params["LFP"])
        if nominal_cycles != params["nominal_cycles"]:
            params["nominal_cycles"] = nominal_cycles

        # Convert cycles to equivalent full cycles using Whittaker-DOD factor
        # N_equiv = N_actual × (DoD / DoD_nominal)^1.8
        total_equivalent_cycles = 0.0
        cycle_histogram: Dict[str, int] = {}

        for dod, count in cycles.items():
            _dod_ratio = dod / nominal_dod if nominal_dod > 0 else 1.0
            equivalent = count * (dod**1.8) / (nominal_dod**1.8)
            total_equivalent_cycles += equivalent
            dod_range = f"{int(dod * 100)}%"
            cycle_histogram[dod_range] = int(count)

        # Temperature derating (Arrhenius)
        R_gas = 8.314e-3  # kJ/(mol·K)
        T_ref = 25.0 + 273.15  # K
        T_op = temperature_C + 273.15  # K
        Ea = params["Ea_kJmol"]

        temp_factor = np.exp(Ea / R_gas * (1.0 / T_ref - 1.0 / T_op))
        # Higher temperature → faster degradation → temp_factor < 1 means reduced life
        temp_factor_life = 1.0 / temp_factor if temp_factor > 0 else 1.0

        # C-rate derating
        c_rate_ref = 0.25
        crate_factor = (c_rate_ref / c_rate) ** 0.3 if c_rate > 0 else 1.0

        # Adjusted cycle life
        adjusted_cycle_life = params["nominal_cycles"] * temp_factor_life * crate_factor

        # Remaining cycles
        remaining_cycles = max(0, adjusted_cycle_life - total_equivalent_cycles)

        # Calendar life check
        n_hours = len(soc_profile)
        operating_years = n_hours / 8760.0
        remaining_calendar_years = max(0, calendar_life_years - operating_years)

        # Estimated total life (cycle or calendar, whichever is limiting)
        cycles_per_year = total_equivalent_cycles / operating_years if operating_years > 0 else 0
        cycle_life_years = (
            remaining_cycles / cycles_per_year if cycles_per_year > 0 else float("inf")
        )
        estimated_total_life_years = min(cycle_life_years, remaining_calendar_years)

        # End-of-life criterion (80% of nominal capacity for most chemistries)
        eol_capacity_pct = params["knees"] * 100.0

        return {
            "battery_chemistry": battery_chemistry,
            "nominal_cycles": params["nominal_cycles"],
            "adjusted_cycle_life": float(adjusted_cycle_life),
            "total_equivalent_cycles": float(total_equivalent_cycles),
            "remaining_cycles": float(remaining_cycles),
            "cycle_utilization_pct": float(total_equivalent_cycles / adjusted_cycle_life * 100.0)
            if adjusted_cycle_life > 0
            else 0.0,
            "cycle_histogram": cycle_histogram,
            "temperature_derating": float(temp_factor_life),
            "crate_derating": float(crate_factor),
            "operating_temperature_C": temperature_C,
            "operating_c_rate": c_rate,
            "calendar_life_years": calendar_life_years,
            "remaining_calendar_years": float(remaining_calendar_years),
            "estimated_remaining_life_years": float(estimated_total_life_years),
            "limiting_factor": "cycles"
            if cycle_life_years < remaining_calendar_years
            else "calendar",
            "eol_capacity_pct": float(eol_capacity_pct),
        }

    @staticmethod
    def _rainflow_count(signal: np.ndarray) -> Dict[float, int]:
        """
        Simplified rainflow cycle counting.

        Counts half-cycles at each range (DoD) level and converts
        to full cycles. Uses a binning approach for efficiency.

        Parameters
        ----------
        signal : np.ndarray
            SOC profile values.

        Returns
        -------
        Dict[float, int]
            Mapping of DoD level to number of cycles.
        """
        # Bin DoD ranges
        dod_bins = np.arange(0.05, 1.05, 0.10)
        cycles: Dict[float, int] = {}

        # Find local extrema
        diff = np.diff(signal)
        extrema_indices = [0]
        for i in range(1, len(diff)):
            if diff[i] * diff[i - 1] < 0:  # Sign change = extremum
                extrema_indices.append(i)
        extrema_indices.append(len(signal) - 1)

        extrema = signal[extrema_indices]

        # Count half-cycles between consecutive extrema
        for i in range(len(extrema) - 1):
            dod = abs(extrema[i + 1] - extrema[i])
            # Bin the DoD
            bin_idx = int(dod / 0.10)
            bin_idx = min(bin_idx, len(dod_bins) - 1)
            dod_key = round(dod_bins[bin_idx], 2)
            cycles[dod_key] = cycles.get(dod_key, 0) + 1

        # Convert half-cycles to full cycles (use float to avoid truncation)
        for key in cycles:
            cycles[key] = cycles[key] / 2

        return cycles

    # ------------------------------------------------------------------
    # Agent execute
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute battery storage analysis task.

        Dispatches based on ``task.parameters['analysis_type']``:
        - ``'sizing'``: BESS sizing optimization
        - ``'dispatch'``: Dispatch strategy optimization
        - ``'roi'``: Financial ROI analysis
        - ``'cycle_life'``: Battery degradation and cycle life
        - ``'full'``: All analyses (default)
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting battery storage analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}
            p = task.parameters

            # Default load profile: synthetic commercial building
            if "load_profile_kw" in p:
                load_profile = np.array(p["load_profile_kw"], dtype=float)
            else:
                load_profile = self._default_load_profile()

            if analysis_type in ("sizing", "full"):
                results["sizing"] = self.size_bess(
                    load_profile_kw=load_profile,
                    target_peak_kw=p.get("target_peak_kw"),
                    max_power_kw=float(p.get("max_power_kw", 1000)),
                    usable_soc_range=tuple(p.get("usable_soc_range", [0.10, 0.90])),
                    round_trip_efficiency=float(p.get("round_trip_efficiency", 0.87)),
                    dod_max=float(p.get("dod_max", 0.90)),
                    discharge_duration_hours=float(p.get("discharge_duration_hours", 4.0)),
                    reserve_margin_pct=float(p.get("reserve_margin_pct", 10.0)),
                )

            if analysis_type in ("dispatch", "full"):
                # Energy prices: synthetic TOU
                if "energy_prices" in p:
                    prices = np.array(p["energy_prices"], dtype=float)
                else:
                    prices = self._default_energy_prices(len(load_profile))

                strategy = p.get("dispatch_strategy", "arbitrage")
                bess_power = float(
                    p.get("bess_power_kw", results.get("sizing", {}).get("power_capacity_kw", 500))
                )
                bess_energy = float(
                    p.get(
                        "bess_energy_kwh",
                        results.get("sizing", {}).get("energy_capacity_kwh", 2000),
                    )
                )

                results["dispatch"] = self.optimize_dispatch(
                    load_profile_kw=load_profile,
                    energy_prices=prices,
                    bess_power_kw=bess_power,
                    bess_energy_kwh=bess_energy,
                    round_trip_efficiency=float(p.get("round_trip_efficiency", 0.87)),
                    strategy=strategy,
                )

            if analysis_type in ("roi", "full"):
                annual_revenue = float(
                    p.get(
                        "annual_revenue_usd",
                        results.get("dispatch", {})
                        .get("financial", {})
                        .get("daily_net_revenue_$", 200)
                        * 365,
                    )
                )
                bess_power = float(p.get("bess_power_kw", 500))
                bess_energy = float(p.get("bess_energy_kwh", 2000))

                results["roi"] = self.calculate_roi(
                    bess_power_kw=bess_power,
                    bess_energy_kwh=bess_energy,
                    annual_revenue_usd=annual_revenue,
                    capex_per_kwh=float(p.get("capex_per_kwh", 300)),
                    capex_per_kw=float(p.get("capex_per_kw", 100)),
                    opex_per_kwh_year=float(p.get("opex_per_kwh_year", 8)),
                    discount_rate=float(p.get("discount_rate", 0.08)),
                    project_life_years=int(p.get("project_life_years", 15)),
                    degradation_pct_year=float(p.get("degradation_pct_year", 2.0)),
                    itc_pct=float(p.get("itc_pct", 30.0)),
                )

            if analysis_type in ("cycle_life", "full"):
                # Use SOC from dispatch if available
                if "dispatch" in results:
                    soc_profile = np.array(results["dispatch"]["schedule"]["soc"])
                else:
                    soc_profile = np.ones(8760) * 0.5  # Flat SOC default

                results["cycle_life"] = self.analyze_cycle_life(
                    soc_profile=soc_profile,
                    battery_chemistry=p.get("battery_chemistry", "LFP"),
                    nominal_cycles=float(p.get("nominal_cycles", 6000)),
                    nominal_dod=float(p.get("nominal_dod", 0.80)),
                    temperature_C=float(p.get("temperature_C", 25.0)),
                    c_rate=float(p.get("c_rate", 0.25)),
                    calendar_life_years=float(p.get("calendar_life_years", 15.0)),
                )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.OPTIMAL_POWER_FLOW,  # closest available
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

            self.log_execution(f"Battery storage analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Battery storage analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.OPTIMAL_POWER_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Default profiles
    # ------------------------------------------------------------------

    @staticmethod
    def _default_load_profile() -> np.ndarray:
        """Generate a synthetic commercial load profile (8760 hours)."""
        hours = 8760
        day_of_year = np.arange(hours) // 24
        hour_of_day = np.arange(hours) % 24

        # Base load
        base = 300.0
        # Peak during business hours (8-18)
        peak = 700.0
        load = np.full(hours, base)
        business_mask = (hour_of_day >= 8) & (hour_of_day <= 18)
        load[business_mask] += peak * np.sin(np.pi * (hour_of_day[business_mask] - 8) / 10.0)

        # Seasonal variation
        seasonal = 1.0 + 0.15 * np.sin(2 * np.pi * (day_of_year - 180) / 365)
        load = load * seasonal

        # Add noise
        np.random.seed(42)
        load += np.random.normal(0, 20, hours)
        return np.maximum(load, 50.0)

    @staticmethod
    def _default_energy_prices(n_periods: int) -> np.ndarray:
        """Generate synthetic TOU energy prices."""
        hour_of_day = np.arange(n_periods) % 24
        # Off-peak: $0.04/kWh (0-6, 22-24)
        # Mid-peak: $0.08/kWh (6-12, 18-22)
        # On-peak: $0.15/kWh (12-18)
        prices = np.where(
            (hour_of_day < 6) | (hour_of_day >= 22),
            0.04,
            np.where((hour_of_day >= 12) & (hour_of_day < 18), 0.15, 0.08),
        )
        return prices

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """Validate battery storage analysis results."""
        errors: List[str] = []

        sizing = result.data.get("sizing")
        if sizing is not None:
            if sizing.get("power_capacity_kw", 0) <= 0:
                errors.append("BESS power capacity is zero or negative")
            if sizing.get("energy_capacity_kwh", 0) <= 0:
                errors.append("BESS energy capacity is zero or negative")
            if sizing.get("round_trip_efficiency", 0) > 1.0:
                errors.append("Round-trip efficiency exceeds 1.0")

        roi = result.data.get("roi")
        if roi is not None:
            if roi.get("npv_$", 0) < -1e9:
                errors.append("NPV is extremely negative — check financial inputs")

        cycle = result.data.get("cycle_life")
        if cycle is not None:
            if cycle.get("cycle_utilization_pct", 0) > 100:
                errors.append("Cycle utilization exceeds 100% — battery end of life")

        result.validation_errors.extend(errors)
        return len(errors) == 0
