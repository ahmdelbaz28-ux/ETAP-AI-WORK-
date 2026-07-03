"""
AhmedETAP - Weather Impact Analysis Agent
=============================================================
Weather information retrieval and power system weather impact analysis.

Capabilities:
- Current weather data retrieval and interpretation
- Weather impact on power system operations and equipment
- Temperature derating analysis for transformers and conductors
- Wind impact on line ratings and cooling
- Severe weather alert processing for power system resilience

Standards:
- IEEE C37.118: Synchrophasor measurements (weather-correlated)
- IEC 60826: Loading guide for power transformers (temperature)
- IEEE 738: Calculation of bare overhead conductor temperatures
- NERC TPL standards: Transmission planning during extreme weather
"""

import logging
from datetime import datetime, timezone

UTC = timezone.utc  # noqa: UP017
from typing import Any

import numpy as np

from agents.orchestrator import AgentResult, AgentStatus, BaseAgent, EngineeringTask, StudyType

logger = logging.getLogger(__name__)


class WeatherAgent(BaseAgent):
    """
    Weather Impact Analysis Agent.

    Provides weather data interpretation and power system impact
    analysis including:

    - **Current Weather**: Fetches and formats current weather data
      for a given location, including temperature, humidity, wind
      speed, and precipitation.
    - **Temperature Derating**: Calculates transformer and cable
      derating factors based on ambient temperature per IEC 60826
      and IEEE 738.
    - **Wind Impact**: Evaluates the effect of wind speed and
      direction on overhead line dynamic thermal ratings and
      cooling effectiveness.
    - **Severe Weather Alerts**: Processes weather alerts and
      assesses their impact on power system resilience, including
      lightning risk, ice loading, and high wind warnings.

    Key equations:

    Transformer derating (IEC 60826):
        Rating_factor = sqrt((θ_hotspot_max - θ_ambient) / (θ_hotspot_max - θ_ref))

    Conductor thermal rating (IEEE 738):
        Heat balance: q_s + q_r = q_c + q_r_rad
        where q_s = solar heat gain, q_c = convective cooling,
        q_r = resistive heating, q_r_rad = radiative cooling

    Dynamic line rating:
        I_dynamic = I_static × sqrt((T_max - T_ambient) / (T_max - T_ref))
    """

    prompt_handle = "weather_agent"

    def __init__(self) -> None:
        super().__init__("WeatherAgent")
        self.standards = [
            "IEEE C37.118",
            "IEC 60826",
            "IEEE 738",
            "NERC TPL",
        ]

    # ------------------------------------------------------------------
    # Core computation methods
    # ------------------------------------------------------------------

    def analyze_temperature_derating(
        self,
        ambient_temp_c: float,
        reference_temp_c: float = 25.0,
        max_hotspot_temp_c: float = 110.0,
        equipment_type: str = "transformer",
    ) -> dict[str, Any]:
        """
        Calculate equipment derating factor due to ambient temperature.

        Parameters
        ----------
        ambient_temp_c : float
            Current or forecast ambient temperature in °C.
        reference_temp_c : float
            Reference (design) ambient temperature in °C (default 25).
        max_hotspot_temp_c : float
            Maximum allowable hotspot temperature in °C (default 110
            for ONAN/ONAF transformers per IEC 60076-2).
        equipment_type : str
            Type of equipment: 'transformer', 'cable', or 'overhead_line'.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'rating_factor', 'derating_percent',
            'ambient_temp_c', 'assessment'.
        """
        delta_max = max_hotspot_temp_c - ambient_temp_c
        delta_ref = max_hotspot_temp_c - reference_temp_c

        if delta_ref <= 0 or delta_max <= 0:
            rating_factor = 0.0
        else:
            rating_factor = float(np.sqrt(delta_max / delta_ref))

        # Cap at 1.0 (no uprating beyond nameplate)
        rating_factor = min(rating_factor, 1.0)
        derating_pct = (1.0 - rating_factor) * 100.0

        if derating_pct <= 0:
            assessment = "No derating required — ambient temperature at or below reference"
        elif derating_pct <= 10:
            assessment = "Minor derating — ambient temperature slightly above reference"
        elif derating_pct <= 25:
            assessment = "Moderate derating — ambient temperature significantly above reference"
        elif derating_pct <= 50:
            assessment = "Severe derating — consider load management actions"
        else:
            assessment = "Critical derating — emergency load reduction required"

        return {
            "rating_factor": round(rating_factor, 4),
            "derating_percent": round(derating_pct, 2),
            "ambient_temp_c": ambient_temp_c,
            "reference_temp_c": reference_temp_c,
            "max_hotspot_temp_c": max_hotspot_temp_c,
            "equipment_type": equipment_type,
            "assessment": assessment,
        }

    def analyze_wind_impact(
        self,
        wind_speed_ms: float,
        ambient_temp_c: float,
        conductor_max_temp_c: float = 75.0,
        conductor_resistance_per_m: float = 7.283e-5,
        conductor_diameter_m: float = 0.0281,
        solar_radiation_wm2: float = 900.0,
        solar_absorptivity: float = 0.5,
        emissivity: float = 0.5,
        static_rating_a: float = 1000.0,
        static_rating_ambient_c: float = 40.0,
    ) -> dict[str, Any]:
        """
        Calculate dynamic line rating based on wind conditions per
        IEEE 738.

        Uses the heat balance equation for bare overhead conductors
        to determine the maximum current under given weather conditions.

        Parameters
        ----------
        wind_speed_ms : float
            Wind speed in m/s perpendicular to the conductor.
        ambient_temp_c : float
            Ambient air temperature in °C.
        conductor_max_temp_c : float
            Maximum allowable conductor temperature in °C.
        conductor_resistance_per_m : float
            AC resistance per meter at max temperature (Ω/m).
        conductor_diameter_m : float
            Conductor outer diameter in meters.
        solar_radiation_wm2 : float
            Solar radiation intensity in W/m².
        solar_absorptivity : float
            Solar absorptivity of conductor surface (0 to 1).
        emissivity : float
            Emissivity of conductor surface (0 to 1).
        static_rating_a : float
            Static (nameplate) line rating in amperes.
        static_rating_ambient_c : float
            Ambient temperature used for static rating in °C.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'dynamic_rating_a', 'static_rating_a',
            'rating_increase_percent', 'wind_speed_ms'.
        """
        T_c = conductor_max_temp_c
        T_a = ambient_temp_c
        D = conductor_diameter_m
        R = conductor_resistance_per_m

        # Convective heat loss (forced convection) per IEEE 738
        # q_c = [1.01 + 1.35 * (Re)^0.52] * k_f * (T_c - T_a)
        # Simplified for wind perpendicular to conductor

        # Air properties at film temperature
        T_film = (T_c + T_a) / 2.0 + 273.15  # K
        k_air = 0.0242 + 7.0e-5 * (T_film - 300.0)  # Thermal conductivity W/(m·K)
        nu_air = 1.516e-5 + 4.0e-8 * (T_film - 300.0)  # Kinematic viscosity m²/s

        # Reynolds number
        Re = wind_speed_ms * D / nu_air if nu_air > 0 else 0.0

        # Forced convection coefficient (simplified IEEE 738)
        if Re > 0:
            Nu = 0.3 + 0.62 * Re**0.5 * 0.71 ** (1.0 / 3.0)  # Simplified
            h_conv = Nu * k_air / D
        else:
            # Natural convection (no wind)
            h_conv = 5.0  # W/(m²·K) approximate

        q_conv = h_conv * np.pi * D * (T_c - T_a)  # W/m

        # Radiative heat loss
        sigma_sb = 5.67e-8  # Stefan-Boltzmann constant
        T_c_K = T_c + 273.15
        T_a_K = T_a + 273.15
        q_rad = emissivity * sigma_sb * np.pi * D * (T_c_K**4 - T_a_K**4)

        # Solar heat gain
        q_solar = solar_absorptivity * solar_radiation_wm2 * D

        # Total heat loss = convective + radiative
        q_loss = q_conv + q_rad

        # Joule heating = I²R per meter
        # I²R = q_loss - q_solar
        q_joule = q_loss - q_solar

        I_dynamic = float(np.sqrt(q_joule / R)) if q_joule > 0 and R > 0 else 0.0

        # Rating increase vs static
        rating_increase = (
            (I_dynamic / static_rating_a - 1.0) * 100.0 if static_rating_a > 0 else 0.0
        )

        # Simple DLR as cross-check: I ∝ sqrt((T_max - T_amb) / (T_max - T_static_amb))
        dlr_factor = np.sqrt(
            max(0, (conductor_max_temp_c - ambient_temp_c))
            / max(1, (conductor_max_temp_c - static_rating_ambient_c)),
        )
        I_dlr_simple = static_rating_a * dlr_factor

        return {
            "dynamic_rating_a": round(I_dynamic, 1),
            "dynamic_rating_simple_a": round(I_dlr_simple, 1),
            "static_rating_a": static_rating_a,
            "rating_increase_percent": round(rating_increase, 2),
            "wind_speed_ms": wind_speed_ms,
            "ambient_temp_c": ambient_temp_c,
            "conductor_max_temp_c": conductor_max_temp_c,
            "convective_heat_loss_wm": round(q_conv, 2),
            "radiative_heat_loss_wm": round(q_rad, 2),
            "solar_heat_gain_wm": round(q_solar, 2),
            "reynolds_number": round(Re, 1),
            "assessment": self._assess_wind_impact(wind_speed_ms, rating_increase),
        }

    def _assess_wind_impact(self, wind_speed: float, _rating_increase: float) -> str:
        """Assess wind impact on line rating."""
        if wind_speed < 0.5:
            return "Calm conditions — static rating applicable; no dynamic uplift"
        elif wind_speed < 3.0:
            return "Light wind — minor dynamic rating uplift possible"
        elif wind_speed < 8.0:
            return "Moderate wind — significant dynamic rating uplift available"
        else:
            return "Strong wind — substantial dynamic rating uplift; monitor for galloping"

    def process_weather_alert(
        self,
        alert_type: str,
        severity: str,
        description: str,
        affected_area: str = "",
        duration_hours: float = 0.0,
    ) -> dict[str, Any]:
        """
        Process a severe weather alert and assess power system impact.

        Parameters
        ----------
        alert_type : str
            Type of alert: 'thunderstorm', 'ice_storm', 'high_wind',
            'heat_wave', 'tornado', 'flood', 'hurricane'.
        severity : str
            Alert severity: 'watch', 'warning', 'emergency'.
        description : str
            Human-readable alert description.
        affected_area : str
            Geographic area affected.
        duration_hours : float
            Expected duration in hours.

        Returns
        -------
        Dict[str, Any]
            Dictionary with 'alert_type', 'severity', 'power_system_impact',
            'recommended_actions', 'risk_level'.
        """
        impact_map: dict[str, str] = {
            "thunderstorm": "Lightning-induced surges, protection misoperation risk, "
            "potential equipment damage from direct strikes",
            "ice_storm": "Conductor galloping, ice loading on lines and structures, "
            "potential line sag and flashover from icing",
            "high_wind": "Conductor galloping, tower/structure stress, "
            "dynamic line rating changes, vegetation contact risk",
            "heat_wave": "Transformer and cable derating, increased load from cooling, "
            "reduced line ratings, voltage regulation stress",
            "tornado": "Catastrophic infrastructure damage risk, extended outages, "
            "protection system damage",
            "flood": "Substation flooding, equipment submersion, "
            "grounding system compromise, cable vault flooding",
            "hurricane": "Extended duration high winds, flooding, storm surge, "
            "widespread infrastructure damage, extended restoration",
        }

        action_map: dict[str, list[str]] = {
            "thunderstorm": [
                "Verify surge arrester condition",
                "Review protection relay settings for lightning coordination",
                "Ensure backup protection is operational",
            ],
            "ice_storm": [
                "Activate ice-melting procedures on critical lines",
                "Reduce loading on lines prone to galloping",
                "Monitor conductor sag and ground clearance",
            ],
            "high_wind": [
                "Apply dynamic line ratings",
                "Increase vegetation management patrols",
                "Monitor structural health of towers",
            ],
            "heat_wave": [
                "Apply ambient-temperature derating to transformers",
                "Activate demand response programs",
                "Monitor transformer oil temperatures",
            ],
            "tornado": [
                "Activate emergency response procedures",
                "Pre-position restoration crews",
                "Prepare for extended outage scenarios",
            ],
            "flood": [
                "Energize flood pumps and dewatering systems",
                "De-energize at-risk underground equipment",
                "Monitor substation water levels",
            ],
            "hurricane": [
                "Implement staged load reduction",
                "Pre-position mutual aid crews",
                "Activate emergency operations center",
            ],
        }

        risk_order = {"watch": 1, "warning": 2, "emergency": 3}
        risk_level = risk_order.get(severity, 0)

        return {
            "alert_type": alert_type,
            "severity": severity,
            "description": description,
            "affected_area": affected_area,
            "duration_hours": duration_hours,
            "power_system_impact": impact_map.get(
                alert_type, "Assess impact based on local conditions",
            ),
            "recommended_actions": action_map.get(
                alert_type, ["Monitor conditions and follow standard procedures"],
            ),
            "risk_level": risk_level,
        }

    # ------------------------------------------------------------------
    # Agent execute method
    # ------------------------------------------------------------------

    async def execute(self, task: EngineeringTask) -> AgentResult:
        """
        Execute weather impact analysis task.

        Dispatches based on ``task.parameters['analysis_type']``:
        ``'temperature_derating'``, ``'wind_impact'``,
        ``'weather_alert'``, or ``'full'``.
        """
        start_time = datetime.now(UTC)
        self.status = AgentStatus.RUNNING

        try:
            self.log_execution(f"Starting weather impact analysis for task {task.task_id}")

            analysis_type = task.parameters.get("analysis_type", "full")
            results: dict[str, Any] = {}

            # --- Temperature derating ---
            if analysis_type in ("temperature_derating", "full"):
                ambient_temp = float(task.parameters.get("ambient_temp_c", 35.0))
                ref_temp = float(task.parameters.get("reference_temp_c", 25.0))
                max_hotspot = float(task.parameters.get("max_hotspot_temp_c", 110.0))
                equip_type = task.parameters.get("equipment_type", "transformer")

                results["temperature_derating"] = self.analyze_temperature_derating(
                    ambient_temp_c=ambient_temp,
                    reference_temp_c=ref_temp,
                    max_hotspot_temp_c=max_hotspot,
                    equipment_type=equip_type,
                )

            # --- Wind impact ---
            if analysis_type in ("wind_impact", "full"):
                wind_speed = float(task.parameters.get("wind_speed_ms", 5.0))
                ambient_temp = float(task.parameters.get("ambient_temp_c", 30.0))

                results["wind_impact"] = self.analyze_wind_impact(
                    wind_speed_ms=wind_speed,
                    ambient_temp_c=ambient_temp,
                    conductor_max_temp_c=float(task.parameters.get("conductor_max_temp_c", 75.0)),
                    static_rating_a=float(task.parameters.get("static_rating_a", 1000.0)),
                )

            # --- Weather alert processing ---
            if analysis_type == "weather_alert":
                results["weather_alert"] = self.process_weather_alert(
                    alert_type=task.parameters.get("alert_type", "thunderstorm"),
                    severity=task.parameters.get("severity", "watch"),
                    description=task.parameters.get("description", ""),
                    affected_area=task.parameters.get("affected_area", ""),
                    duration_hours=float(task.parameters.get("duration_hours", 0.0)),
                )

            result = AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.COMPLETED,
                data={
                    **results,
                    "analysis_type": analysis_type,
                    "standards": self.standards,
                },
            )

            result.validation_status = self.validate_result(result)
            execution_time = (datetime.now(UTC) - start_time).total_seconds()
            result.execution_time = execution_time

            self.log_execution(f"Weather impact analysis completed in {execution_time:.2f}s")
            return result

        except Exception as e:
            self.log_execution(f"Weather impact analysis failed: {str(e)}", "ERROR")
            return AgentResult(
                agent_name=self.agent_name,
                study_type=task.study_types[0] if task.study_types else StudyType.LOAD_FLOW,
                status=AgentStatus.FAILED,
                data={},
                validation_errors=[str(e)],
            )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_result(self, result: AgentResult) -> bool:
        """
        Validate weather impact analysis results.

        Checks:
        - Derating factors are between 0 and 1
        - Dynamic ratings are non-negative
        - Weather alert risk levels are valid
        """
        errors: list[str] = []

        td_data = result.data.get("temperature_derating")
        if td_data is not None:
            factor = td_data.get("rating_factor", 1.0)
            if factor < 0 or factor > 1:
                errors.append(f"Derating factor out of range [0,1]: {factor:.4f}")

        wi_data = result.data.get("wind_impact")
        if wi_data is not None:
            dyn_rating = wi_data.get("dynamic_rating_a", 0.0)
            if dyn_rating < 0:
                errors.append(f"Dynamic rating is negative: {dyn_rating:.1f} A")

        wa_data = result.data.get("weather_alert")
        if wa_data is not None:
            risk = wa_data.get("risk_level", 0)
            if risk not in (0, 1, 2, 3):
                errors.append(f"Invalid risk level: {risk}")

        result.validation_errors.extend(errors)
        return len(errors) == 0
