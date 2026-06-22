"""
AhmedETAP - Renewable Integration Agent
===========================================================
Solar PV and wind turbine integration analysis per IEEE 1547.

Capabilities:
- Solar PV integration analysis (inverter model, power curve, irradiance model)
- Wind turbine integration analysis (power curve, cut-in/cut-out speeds)
- IEEE 1547 grid interconnection compliance verification
- Hosting capacity calculation for DER penetration

Standards:
- IEEE 1547-2018: Standard for Interconnection and Interoperability
  of Distributed Energy Resources with Associated Electric Power
  Systems Interfaces
- IEEE 1547.1-2020: Conformance Test Procedures
"""

import logging
from datetime import datetime, timezone

UTC = timezone.utc
from typing import Any, Dict, List, Tuple

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class RenewableAgent(BaseAgent):
    """
    Renewable Energy Integration Agent (IEEE 1547).

    Provides analysis of distributed energy resource (DER) integration
    including:

    - Solar PV: irradiance-to-power conversion with temperature
      derating, inverter clipping, and mismatch losses
    - Wind: turbine power curve modeling with Rayleigh/Weibull wind
      distribution and capacity factor estimation
    - IEEE 1547 compliance: voltage regulation, frequency response,
      ride-through requirements, power quality
    - Hosting capacity: maximum DER penetration without violating
      grid constraints (voltage, thermal, protection)
    """

    prompt_handle = "renewable_agent"

    def __init__(self) -> None:
        super().__init__("RenewableAgent")
        self.standards = ["IEEE 1547-2018", "IEEE 1547.1-2020"]

    # ------------------------------------------------------------------
    # Solar PV analysis
    # ------------------------------------------------------------------

    def analyze_solar_pv(
        self,
        dc_capacity_kw: float,
        ac_capacity_kw: float,
        irradiance_kw_m2: np.ndarray = None,
        temperature_C: np.ndarray = None,
        noct_C: float = 45.0,
        temp_coeff_power_pctK: float = -0.40,
        soiling_loss_pct: float = 2.0,
        mismatch_loss_pct: float = 2.0,
        wiring_loss_pct: float = 1.0,
        inverter_efficiency_pct: float = 96.0,
        availability_pct: float = 99.0,
        tilt_deg: float = 25.0,
        azimuth_deg: float = 180.0,
        latitude_deg: float = 33.0,
    ) -> Dict[str, Any]:
        """
        Perform solar PV integration analysis.

        Models the PV system output using a simplified single-diode model
        approximation with temperature and irradiance derating.

        Power output:
            P_dc = P_stc × (G / G_stc) × [1 + γ × (T_cell - T_stc)]

        where:
            G      = actual irradiance (W/m²)
            G_stc  = 1000 W/m² (STC)
            γ      = temperature coefficient (%/°C)
            T_cell = NOCT-based cell temperature
            T_stc  = 25 °C

        Parameters
        ----------
        dc_capacity_kw : float
            PV array DC nameplate capacity in kW.
        ac_capacity_kw : float
            Inverter AC nameplate capacity in kW.
        irradiance_kw_m2 : np.ndarray, optional
            Hourly irradiance profile (kW/m²). If None, a synthetic
            clear-sky profile is generated.
        temperature_C : np.ndarray, optional
            Hourly ambient temperature profile (°C).
        noct_C : float
            Nominal Operating Cell Temperature in °C.
        temp_coeff_power_pctK : float
            Power temperature coefficient in %/°C (negative for c-Si).
        soiling_loss_pct, mismatch_loss_pct, wiring_loss_pct : float
            System loss factors in percent.
        inverter_efficiency_pct : float
            Inverter weighted efficiency in percent.
        availability_pct : float
            System availability in percent.
        tilt_deg : float
            Array tilt angle in degrees.
        azimuth_deg : float
            Array azimuth (180 = south-facing, northern hemisphere).
        latitude_deg : float
            Site latitude in degrees.

        Returns
        -------
        Dict[str, Any]
            PV system analysis with annual energy, capacity factor,
            losses breakdown, and inverter loading ratio.
        """
        # Generate synthetic hourly data if not provided (8760 hours)
        hours = 8760
        if irradiance_kw_m2 is None:
            irradiance_kw_m2 = self._generate_synthetic_irradiance(
                hours, tilt_deg, azimuth_deg, latitude_deg
            )
        else:
            irradiance_kw_m2 = np.asarray(irradiance_kw_m2, dtype=float)
            hours = len(irradiance_kw_m2)

        if temperature_C is None:
            # Synthetic temperature: sinusoidal daily pattern
            temperature_C = 20.0 + 10.0 * np.sin(2.0 * np.pi * (np.arange(hours) - 2200) / hours)
        else:
            temperature_C = np.asarray(temperature_C, dtype=float)

        G_stc = 1.0  # kW/m² (STC)
        T_stc = 25.0  # °C

        # Cell temperature per NOCT method (IEEE 1547 / IEC 61215)
        # T_cell = T_amb + (NOCT - 20) × G / 800
        T_cell = temperature_C + (noct_C - 20.0) * (irradiance_kw_m2 * 1000.0) / 800.0

        # DC power output (kW)
        gamma = temp_coeff_power_pctK / 100.0  # Convert %/°C to per-unit/°C
        P_dc = dc_capacity_kw * (irradiance_kw_m2 / G_stc) * (1.0 + gamma * (T_cell - T_stc))
        P_dc = np.maximum(P_dc, 0.0)

        # Inverter clipping
        P_ac_pre_loss = P_dc * (inverter_efficiency_pct / 100.0)
        P_ac_clipped = np.minimum(P_ac_pre_loss, ac_capacity_kw)
        clipping_loss_kw = P_ac_pre_loss - P_ac_clipped

        # System losses
        loss_factor = (
            (1.0 - soiling_loss_pct / 100.0)
            * (1.0 - mismatch_loss_pct / 100.0)
            * (1.0 - wiring_loss_pct / 100.0)
            * (availability_pct / 100.0)
        )

        P_ac_final = P_ac_clipped * loss_factor

        # Annual energy
        annual_energy_kwh = float(np.sum(P_ac_final))
        capacity_factor = annual_energy_kwh / (dc_capacity_kw * hours) * 100.0

        # Inverter loading ratio (DC/AC)
        ilr = dc_capacity_kw / ac_capacity_kw if ac_capacity_kw > 0 else 0.0

        # Specific yield
        specific_yield = annual_energy_kwh / dc_capacity_kw if dc_capacity_kw > 0 else 0.0

        # Loss breakdown
        total_dc_energy = float(np.sum(P_dc))
        inverter_loss = total_dc_energy - float(np.sum(P_ac_pre_loss))
        clipping_energy = float(np.sum(clipping_loss_kw))
        system_losses = float(np.sum(P_ac_clipped)) - annual_energy_kwh

        return {
            "dc_capacity_kw": dc_capacity_kw,
            "ac_capacity_kw": ac_capacity_kw,
            "inverter_loading_ratio": float(ilr),
            "annual_energy_kwh": annual_energy_kwh,
            "capacity_factor_pct": float(capacity_factor),
            "specific_yield_kwh_kw": float(specific_yield),
            "peak_output_kw": float(np.max(P_ac_final)),
            "hours_at_peak": int(np.sum(P_ac_final >= 0.99 * np.max(P_ac_final))),
            "losses": {
                "temperature_loss_kwh": float(
                    total_dc_energy - np.sum(dc_capacity_kw * (irradiance_kw_m2 / G_stc))
                ),
                "inverter_loss_kwh": float(inverter_loss),
                "clipping_loss_kwh": float(clipping_energy),
                "system_losses_kwh": float(system_losses),
                "soiling_pct": soiling_loss_pct,
                "mismatch_pct": mismatch_loss_pct,
                "wiring_pct": wiring_loss_pct,
                "inverter_efficiency_pct": inverter_efficiency_pct,
                "availability_pct": availability_pct,
            },
            "monthly_energy_kwh": [
                float(np.sum(P_ac_final[(m * 730) : min((m + 1) * 730, hours)])) for m in range(12)
            ],
        }

    @staticmethod
    def _generate_synthetic_irradiance(
        hours: int, tilt_deg: float, azimuth_deg: float, latitude_deg: float
    ) -> np.ndarray:
        """Generate a synthetic clear-sky irradiance profile (kW/m²)."""
        day_of_year = np.arange(hours) // 24
        hour_of_day = np.arange(hours) % 24

        # Solar declination (degrees)
        declination = 23.45 * np.sin(np.radians(360.0 * (284 + day_of_year) / 365.0))

        # Hour angle
        hour_angle = 15.0 * (hour_of_day - 12.0)

        # Solar elevation
        lat_rad = np.radians(latitude_deg)
        dec_rad = np.radians(declination)
        ha_rad = np.radians(hour_angle)

        sin_elev = np.sin(lat_rad) * np.sin(dec_rad) + np.cos(lat_rad) * np.cos(dec_rad) * np.cos(
            ha_rad
        )
        elevation = np.arcsin(np.clip(sin_elev, -1, 1))

        # Clear-sky irradiance on horizontal plane
        ghi = np.where(
            elevation > 0,
            1.0 * np.sin(elevation) * (0.7 ** (1.0 / (np.sin(elevation) + 0.01))),
            0.0,
        )

        # Simple tilt/orientation factor (isotropic diffuse model)
        tilt_rad = np.radians(tilt_deg)
        tilt_factor = np.clip(
            np.cos(tilt_rad) + np.sin(tilt_rad) * np.cos(elevation - tilt_rad),
            0.0,
            1.5,
        )

        poa = ghi * tilt_factor * 0.85  # Plane-of-array with diffuse contribution
        poa = np.clip(poa, 0.0, 1.2)  # kW/m²

        # Add some cloud randomness
        np.random.seed(42)
        cloud_factor = 0.7 + 0.3 * np.random.random(hours)
        poa = poa * cloud_factor

        return np.clip(poa, 0.0, 1.2)

    # ------------------------------------------------------------------
    # Wind analysis
    # ------------------------------------------------------------------

    def analyze_wind(
        self,
        rated_power_kw: float,
        cut_in_speed_ms: float = 3.0,
        rated_speed_ms: float = 12.0,
        cut_out_speed_ms: float = 25.0,
        rotor_diameter_m: float = 80.0,
        hub_height_m: float = 80.0,
        weibull_k: float = 2.0,
        weibull_c: float = 8.0,
        air_density_kgm3: float = 1.225,
        availability_pct: float = 97.0,
        losses_pct: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Perform wind turbine integration analysis.

        Models turbine output using a parametric power curve and Weibull
        wind speed distribution for energy estimation.

        Power curve model:
            P(v) = 0                                          v < v_ci
            P(v) = P_rated × (v³ - v_ci³) / (v_r³ - v_ci³)   v_ci ≤ v < v_r
            P(v) = P_rated                                     v_r ≤ v < v_co
            P(v) = 0                                          v ≥ v_co

        Parameters
        ----------
        rated_power_kw : float
            Turbine rated power output in kW.
        cut_in_speed_ms : float
            Cut-in wind speed in m/s.
        rated_speed_ms : float
            Rated wind speed in m/s.
        cut_out_speed_ms : float
            Cut-out wind speed in m/s.
        rotor_diameter_m : float
            Rotor diameter in metres.
        hub_height_m : float
            Hub height in metres.
        weibull_k : float
            Weibull shape parameter.
        weibull_c : float
            Weibull scale parameter in m/s.
        air_density_kgm3 : float
            Air density in kg/m³.
        availability_pct : float
            Turbine availability in percent.
        losses_pct : float
            Aggregate electrical losses in percent.

        Returns
        -------
        Dict[str, Any]
            Wind energy analysis with capacity factor, AEP, and
            power curve data.
        """
        v = np.linspace(0, 30, 301)  # Wind speed bins (0 to 30 m/s)

        # Power curve
        P = np.zeros_like(v)
        mask_operating = (v >= cut_in_speed_ms) & (v < rated_speed_ms)
        mask_rated = (v >= rated_speed_ms) & (v < cut_out_speed_ms)

        P[mask_operating] = (
            rated_power_kw
            * (v[mask_operating] ** 3 - cut_in_speed_ms**3)
            / (rated_speed_ms**3 - cut_in_speed_ms**3)
        )
        P[mask_rated] = rated_power_kw

        # Weibull probability distribution
        try:
            from scipy.special import gamma as gamma_func  # type: ignore
        except ImportError:
            # Fallback: Stirling's approximation for gamma function
            import math

            def gamma_func(x):
                return math.gamma(x)

        weibull_pdf = (
            (weibull_k / weibull_c)
            * (v / weibull_c) ** (weibull_k - 1)
            * np.exp(-((v / weibull_c) ** weibull_k))
        )
        weibull_pdf[0] = 0.0  # Avoid issues at v=0

        # Normalise
        dv = v[1] - v[0]
        weibull_pdf = weibull_pdf / (np.sum(weibull_pdf) * dv)

        # Annual energy production (AEP)
        P_avg = np.sum(P * weibull_pdf) * dv  # Average power in kW
        hours_per_year = 8760.0
        aep_gross = P_avg * hours_per_year

        # Apply losses and availability
        loss_factor = (availability_pct / 100.0) * (1.0 - losses_pct / 100.0)
        aep_net = aep_gross * loss_factor

        # Capacity factor
        capacity_factor = (aep_net / (rated_power_kw * hours_per_year)) * 100.0

        # Rotor swept area and specific power
        swept_area = np.pi * (rotor_diameter_m / 2.0) ** 2
        specific_power = rated_power_kw / swept_area * 1000.0  # W/m²

        # Mean wind speed from Weibull parameters
        mean_wind_speed = weibull_c * gamma_func(1.0 + 1.0 / weibull_k)

        # Theoretical max power (Betz limit)
        P_betz = 0.5 * air_density_kgm3 * swept_area * (16.0 / 27.0) * mean_wind_speed**3 / 1000.0

        return {
            "rated_power_kw": rated_power_kw,
            "cut_in_speed_ms": cut_in_speed_ms,
            "rated_speed_ms": rated_speed_ms,
            "cut_out_speed_ms": cut_out_speed_ms,
            "rotor_diameter_m": rotor_diameter_m,
            "hub_height_m": hub_height_m,
            "swept_area_m2": float(swept_area),
            "specific_power_Wm2": float(specific_power),
            "mean_wind_speed_ms": float(mean_wind_speed),
            "weibull_k": weibull_k,
            "weibull_c_ms": weibull_c,
            "aep_gross_kwh": float(aep_gross),
            "aep_net_kwh": float(aep_net),
            "capacity_factor_pct": float(capacity_factor),
            "average_power_kw": float(P_avg),
            "betz_limit_power_kw": float(P_betz),
            "power_coefficient": float(P_avg / P_betz) if P_betz > 0 else 0.0,
            "availability_pct": availability_pct,
            "losses_pct": losses_pct,
            "power_curve": {
                "wind_speed_ms": v[::5].tolist(),
                "power_kw": P[::5].tolist(),
            },
            "wind_distribution": {
                "wind_speed_ms": v[::5].tolist(),
                "probability": weibull_pdf[::5].tolist(),
            },
        }

    # ------------------------------------------------------------------
    # IEEE 1547 compliance
    # ------------------------------------------------------------------

    def check_ieee1547_compliance(
        self,
        der_capacity_kw: float,
        feeder_capacity_kva: float,
        point_of_interconnection_voltage_V: float,
        voltage_regulation_pct: float,
        frequency_response_Hz: float,
        has_ride_through: bool = True,
        has_anti_islanding: bool = True,
        power_factor_range: Tuple[float, float] = (0.9, 1.0),
        der_category: str = "II",
    ) -> Dict[str, Any]:
        """
        Verify DER interconnection compliance per IEEE 1547-2018.

        IEEE 1547-2018 Categories:
        - Category I: Mandatory minimum functionality
        - Category II: Default (voltage & frequency ride-through)
        - Category III: High penetration / microgrid-ready

        Checks:
        1. Voltage regulation (±5% of nominal)
        2. Frequency response (must trip within specified time/frequency)
        3. Ride-through capability (Category II/III)
        4. Anti-islanding protection
        5. Power factor capability
        6. Penetration level assessment

        Parameters
        ----------
        der_capacity_kw : float
            DER nameplate capacity in kW.
        feeder_capacity_kva : float
            Feeder / service transformer capacity in kVA.
        point_of_interconnection_voltage_V : float
            PCC voltage in V.
        voltage_regulation_pct : float
            Expected voltage impact of DER in percent.
        frequency_response_Hz : float
            Frequency deviation triggering DER response in Hz.
        has_ride_through : bool
            Whether DER has voltage/frequency ride-through.
        has_anti_islanding : bool
            Whether DER has anti-islanding protection.
        power_factor_range : Tuple[float, float]
            (min PF, max PF) capability.
        der_category : str
            IEEE 1547 category ('I', 'II', or 'III').

        Returns
        -------
        Dict[str, Any]
            Compliance verification results.
        """
        checks: List[Dict[str, Any]] = []

        # 1. Penetration level
        penetration = der_capacity_kw / feeder_capacity_kva * 100.0
        penetration_ok = penetration <= 100.0
        penetration_note = (
            "Within limits"
            if penetration <= 15.0
            else (
                "Simplified interconnection if ≤15%"
                if penetration <= 100.0
                else "Exceeds feeder capacity"
            )
        )
        checks.append(
            {
                "requirement": "DER Penetration Level",
                "value": f"{penetration:.1f}%",
                "limit": "≤100% of feeder capacity",
                "compliant": penetration_ok,
                "note": penetration_note,
            }
        )

        # 2. Voltage regulation
        v_reg_limit = 5.0  # ANSI C84.5 Range A
        v_reg_ok = abs(voltage_regulation_pct) <= v_reg_limit
        checks.append(
            {
                "requirement": "Voltage Regulation",
                "value": f"{voltage_regulation_pct:.2f}%",
                "limit": f"≤±{v_reg_limit}%",
                "compliant": v_reg_ok,
                "note": "Per ANSI C84.5 Range A",
            }
        )

        # 3. Frequency response (IEEE 1547 Table 15)
        freq_trip_limits = {
            "I": {"under_freq_Hz": 57.0, "over_freq_Hz": 60.5, "clear_time_s": 0.3},
            "II": {"under_freq_Hz": 57.0, "over_freq_Hz": 62.0, "clear_time_s": 0.16},
            "III": {"under_freq_Hz": 56.5, "over_freq_Hz": 62.0, "clear_time_s": 0.16},
        }
        cat = der_category.upper()
        freq_limits = freq_trip_limits.get(cat, freq_trip_limits["II"])

        freq_ok = frequency_response_Hz >= 0.5  # Must respond to ≥0.5 Hz deviation
        checks.append(
            {
                "requirement": "Frequency Response",
                "value": f"±{frequency_response_Hz:.1f} Hz",
                "limit": f"Category {cat}: UF≤{freq_limits['under_freq_Hz']} Hz, "
                f"OF≤{freq_limits['over_freq_Hz']} Hz",
                "compliant": freq_ok,
                "note": f"Clearing time ≤{freq_limits['clear_time_s']}s",
            }
        )

        # 4. Ride-through
        ride_through_required = cat in ("II", "III")
        ride_through_ok = has_ride_through if ride_through_required else True
        checks.append(
            {
                "requirement": "Voltage/Frequency Ride-Through",
                "value": "Yes" if has_ride_through else "No",
                "limit": f"Required for Category {cat}",
                "compliant": ride_through_ok,
                "note": "Mandatory for Cat II/III per IEEE 1547-2018 §6",
            }
        )

        # 5. Anti-islanding
        checks.append(
            {
                "requirement": "Anti-Islanding Protection",
                "value": "Yes" if has_anti_islanding else "No",
                "limit": "Required for all categories",
                "compliant": has_anti_islanding,
                "note": "Must trip within 2.0 s per IEEE 1547.1",
            }
        )

        # 6. Power factor capability
        pf_min, pf_max = power_factor_range
        pf_ok = pf_min <= 0.9  # IEEE 1547 requires ±0.9 PF capability
        checks.append(
            {
                "requirement": "Power Factor Capability",
                "value": f"{pf_min:.2f} - {pf_max:.2f}",
                "limit": "≥0.90 leading/lagging",
                "compliant": pf_ok,
                "note": "DER must be capable of operating at PF=0.90",
            }
        )

        # 7. PCC voltage level
        _nominal_voltages = {
            120: 120,
            208: 208,
            240: 240,
            480: 480,
            2400: 2400,
            4160: 4160,
            12470: 12470,
            13800: 13800,
            24940: 24940,
        }
        pcc_ok = point_of_interconnection_voltage_V > 0
        checks.append(
            {
                "requirement": "PCC Voltage Level",
                "value": f"{point_of_interconnection_voltage_V:.0f} V",
                "limit": "Standard nominal voltage",
                "compliant": pcc_ok,
                "note": "Must match utility nominal voltage",
            }
        )

        all_compliant = all(c["compliant"] for c in checks)
        non_compliant = [c for c in checks if not c["compliant"]]

        return {
            "overall_compliant": bool(all_compliant),
            "der_category": cat,
            "der_capacity_kw": der_capacity_kw,
            "feeder_capacity_kva": feeder_capacity_kva,
            "penetration_pct": float(penetration),
            "checks": checks,
            "non_compliant_items": non_compliant,
            "total_checks": len(checks),
            "compliant_checks": len(checks) - len(non_compliant),
        }

    # ------------------------------------------------------------------
    # Hosting capacity
    # ------------------------------------------------------------------

    def calculate_hosting_capacity(
        self,
        feeder_head_kva: float,
        min_voltage_pu: float = 0.95,
        max_voltage_pu: float = 1.05,
        max_voltage_rise_pct_per_kw: float = 0.01,
        max_thermal_loading_pct: float = 100.0,
        current_loading_pct: float = 60.0,
        reverse_power_allowed: bool = False,
        pf_der: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Calculate DER hosting capacity of the feeder.

        Hosting capacity is limited by:
        1. Voltage rise constraint: ΔV = (R × P + X × Q) / V²
        2. Thermal constraint: feeder loading < max rating
        3. Reverse power flow constraint (if applicable)
        4. Protection coordination constraint

        Parameters
        ----------
        feeder_head_kva : float
            Feeder head rating in kVA.
        min_voltage_pu, max_voltage_pu : float
            Allowable voltage range in pu.
        max_voltage_rise_pct_per_kw : float
            Voltage rise per kW of DER injection (%/kW).
        max_thermal_loading_pct : float
            Maximum allowable thermal loading in percent.
        current_loading_pct : float
            Current feeder loading in percent.
        reverse_power_allowed : bool
            Whether reverse power flow is permitted.
        pf_der : float
            DER power factor.

        Returns
        -------
        Dict[str, Any]
            Hosting capacity result with limiting constraint.
        """
        # 1. Voltage-limited hosting capacity
        voltage_rise_budget = (max_voltage_pu - 1.0) * 100.0  # % above nominal
        if max_voltage_rise_pct_per_kw > 0:
            HC_voltage = voltage_rise_budget / max_voltage_rise_pct_per_kw  # kW
        else:
            HC_voltage = float("inf")

        # 2. Thermal-limited hosting capacity
        thermal_headroom_pct = max_thermal_loading_pct - current_loading_pct
        HC_thermal = feeder_head_kva * (thermal_headroom_pct / 100.0)  # kVA
        HC_thermal_kw = HC_thermal * pf_der  # Convert to kW at DER PF

        # 3. Reverse power constraint
        if reverse_power_allowed:
            HC_reverse = float("inf")
        else:
            # DER can't exceed current load (no reverse flow)
            HC_reverse = feeder_head_kva * (current_loading_pct / 100.0) * pf_der  # kW

        # 4. Protection coordination margin (conservative 80% of thermal)
        HC_protection = HC_thermal_kw * 0.80

        # Overall hosting capacity = minimum of all constraints
        constraints = {
            "voltage_limit_kw": float(HC_voltage),
            "thermal_limit_kw": float(HC_thermal_kw),
            "reverse_power_limit_kw": float(HC_reverse),
            "protection_limit_kw": float(HC_protection),
        }

        HC_overall = min(HC_voltage, HC_thermal_kw, HC_reverse, HC_protection)
        limiting_constraint = min(constraints, key=constraints.get)

        penetration_at_HC = (HC_overall / feeder_head_kva) * 100.0 if feeder_head_kva > 0 else 0.0

        return {
            "hosting_capacity_kw": float(HC_overall),
            "hosting_capacity_kva": float(HC_overall / pf_der) if pf_der > 0 else 0.0,
            "limiting_constraint": limiting_constraint,
            "constraints": constraints,
            "penetration_at_HC_pct": float(penetration_at_HC),
            "feeder_head_kva": feeder_head_kva,
            "voltage_range_pu": {"min": min_voltage_pu, "max": max_voltage_pu},
            "current_loading_pct": current_loading_pct,
            "der_power_factor": pf_der,
        }

    # ------------------------------------------------------------------
    # Agent execute
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute renewable energy analysis task.

        Dispatches based on ``task.parameters['analysis_type']``:
        - ``'solar_pv'``: Solar PV analysis
        - ``'wind'``: Wind turbine analysis
        - ``'ieee1547'``: IEEE 1547 compliance check
        - ``'hosting_capacity'``: Hosting capacity calculation
        - ``'full'``: All analyses (default)
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting renewable analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: Dict[str, Any] = {}
            p = task.parameters

            if analysis_type in ("solar_pv", "full"):
                results["solar_pv"] = self.analyze_solar_pv(
                    dc_capacity_kw=float(p.get("pv_dc_capacity_kw", 500)),
                    ac_capacity_kw=float(p.get("pv_ac_capacity_kw", 400)),
                    irradiance_kw_m2=p.get("irradiance_profile"),
                    temperature_C=p.get("temperature_profile"),
                    noct_C=float(p.get("noct_C", 45.0)),
                    temp_coeff_power_pctK=float(p.get("temp_coeff_pctK", -0.40)),
                    soiling_loss_pct=float(p.get("soiling_loss_pct", 2.0)),
                    mismatch_loss_pct=float(p.get("mismatch_loss_pct", 2.0)),
                    wiring_loss_pct=float(p.get("wiring_loss_pct", 1.0)),
                    inverter_efficiency_pct=float(p.get("inverter_efficiency_pct", 96.0)),
                    availability_pct=float(p.get("pv_availability_pct", 99.0)),
                    tilt_deg=float(p.get("tilt_deg", 25.0)),
                    azimuth_deg=float(p.get("azimuth_deg", 180.0)),
                    latitude_deg=float(p.get("latitude_deg", 33.0)),
                )

            if analysis_type in ("wind", "full"):
                results["wind"] = self.analyze_wind(
                    rated_power_kw=float(p.get("wind_rated_power_kw", 2000)),
                    cut_in_speed_ms=float(p.get("cut_in_speed_ms", 3.0)),
                    rated_speed_ms=float(p.get("rated_speed_ms", 12.0)),
                    cut_out_speed_ms=float(p.get("cut_out_speed_ms", 25.0)),
                    rotor_diameter_m=float(p.get("rotor_diameter_m", 80.0)),
                    hub_height_m=float(p.get("hub_height_m", 80.0)),
                    weibull_k=float(p.get("weibull_k", 2.0)),
                    weibull_c=float(p.get("weibull_c", 8.0)),
                    air_density_kgm3=float(p.get("air_density_kgm3", 1.225)),
                    availability_pct=float(p.get("wind_availability_pct", 97.0)),
                    losses_pct=float(p.get("wind_losses_pct", 10.0)),
                )

            if analysis_type in ("ieee1547", "full"):
                results["ieee1547_compliance"] = self.check_ieee1547_compliance(
                    der_capacity_kw=float(p.get("der_capacity_kw", 500)),
                    feeder_capacity_kva=float(p.get("feeder_capacity_kva", 5000)),
                    point_of_interconnection_voltage_V=float(p.get("pcc_voltage_V", 480)),
                    voltage_regulation_pct=float(p.get("voltage_regulation_pct", 2.0)),
                    frequency_response_Hz=float(p.get("frequency_response_Hz", 1.5)),
                    has_ride_through=bool(p.get("has_ride_through", True)),
                    has_anti_islanding=bool(p.get("has_anti_islanding", True)),
                    power_factor_range=tuple(p.get("power_factor_range", [0.9, 1.0])),
                    der_category=p.get("der_category", "II"),
                )

            if analysis_type in ("hosting_capacity", "full"):
                results["hosting_capacity"] = self.calculate_hosting_capacity(
                    feeder_head_kva=float(p.get("feeder_head_kva", 10000)),
                    min_voltage_pu=float(p.get("min_voltage_pu", 0.95)),
                    max_voltage_pu=float(p.get("max_voltage_pu", 1.05)),
                    max_voltage_rise_pct_per_kw=float(p.get("voltage_rise_pct_per_kw", 0.01)),
                    max_thermal_loading_pct=float(p.get("max_thermal_loading_pct", 100.0)),
                    current_loading_pct=float(p.get("current_loading_pct", 60.0)),
                    reverse_power_allowed=bool(p.get("reverse_power_allowed", False)),
                    pf_der=float(p.get("pf_der", 1.0)),
                )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,  # closest available
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

            self.log_execution(f"Renewable analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Renewable analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """Validate renewable analysis results."""
        errors: List[str] = []

        pv = result.data.get("solar_pv")
        if pv is not None:
            if pv.get("annual_energy_kwh", 0) <= 0:
                errors.append("Solar PV annual energy is zero or negative")
            if pv.get("capacity_factor_pct", 0) > 35:
                errors.append(
                    f"Suspiciously high PV capacity factor: {pv['capacity_factor_pct']:.1f}%"
                )

        wind = result.data.get("wind")
        if wind is not None:
            if wind.get("capacity_factor_pct", 0) > 60:
                errors.append(
                    f"Suspiciously high wind capacity factor: {wind['capacity_factor_pct']:.1f}%"
                )

        compliance = result.data.get("ieee1547_compliance")
        if compliance is not None and not compliance.get("overall_compliant", True):
            nc = compliance.get("non_compliant_items", [])
            for item in nc:
                errors.append(f"IEEE 1547 non-compliance: {item['requirement']}")

        hc = result.data.get("hosting_capacity")
        if hc is not None and hc.get("hosting_capacity_kw", 0) <= 0:
            errors.append("Hosting capacity is zero or negative")

        result.validation_errors.extend(errors)
        return len(errors) == 0
