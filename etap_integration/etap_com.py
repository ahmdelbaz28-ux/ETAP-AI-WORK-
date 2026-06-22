"""
ETAP COM Automation Interface
==============================
Provides direct integration with ETAP Power System software via COM automation.

Requirements:
- Windows OS
- ETAP installed (v12.0 or later)
- pywin32 package

Usage:
    from etap_com import ETAPAutomation
    etap = ETAPAutomation()
    etap.launch()
    project = etap.open_project("C:\\Projects\\MyProject.edb")
    results = project.run_load_flow()
    etap.close()
"""

import logging
import os
import pathlib
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Only import on Windows
if sys.platform == "win32":
    try:
        import pythoncom
        import win32com.client

        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
        logger.warning("pywin32 not available. ETAP COM automation disabled.")
else:
    WIN32_AVAILABLE = False

# =============================================================================
# Module-level size and range limits
# =============================================================================
MAX_RESULT_ENTRIES = 100000
MAX_PROJECT_PATH_LENGTH = 4096
MAX_BUS_NAME_LENGTH = 256
MAX_STRING_INPUT_LENGTH = 10000
MAX_NUMERIC_VALUE = 1e15
MIN_NUMERIC_VALUE = -1e15
MAX_RECURSION_DEPTH = 50

# Engineering parameter validation ranges
VOLTAGE_MIN = 0.1
VOLTAGE_MAX = 1200.0
CURRENT_MIN = 0.0
CURRENT_MAX = 500000.0
POWER_MIN = -100000.0
POWER_MAX = 100000.0
ANGLE_MIN = -360.0
ANGLE_MAX = 360.0
DURATION_MIN = 0.0
DURATION_MAX = 10000.0
FREQUENCY_MIN = 0.0
FREQUENCY_MAX = 1000.0
WORKING_DISTANCE_MIN = 50.0
WORKING_DISTANCE_MAX = 50000.0
TMS_MIN = 0.025
TMS_MAX = 10.0
PICKUP_CURRENT_MIN = 0.1
PICKUP_CURRENT_MAX = 10000.0

VALID_FAULT_TYPES = {"ThreePhase", "LineToGround", "LineToLine", "DoubleLineToGround"}

# Attempt to import the security-framework InputValidator for reuse
try:
    from security.security_framework import InputValidator as _BaseValidator  # noqa: F401

    HAS_INPUT_VALIDATOR = True
except ImportError:
    HAS_INPUT_VALIDATOR = False


class ETAPStudyType(Enum):
    """ETAP study types."""

    LOAD_FLOW = "LoadFlow"
    SHORT_CIRCUIT = "ShortCircuit"
    MOTOR_ACCELERATION = "MotorAcceleration"
    MOTOR_STARTING = "MotorStarting"
    TRANSIENT_STABILITY = "TransientStability"
    HARMONIC_ANALYSIS = "HarmonicAnalysis"
    OPTIMAL_POWER_FLOW = "OptimalPowerFlow"
    PROTECTION_COORDINATION = "ProtectionCoordination"
    ARC_FLASH = "ArcFlash"
    CABLE_AMACITY = "CableAmpacity"
    GROUND_GRID = "GroundGrid"
    RELIABILITY = "Reliability"


# =============================================================================
# Per-study-type parameter schemas
# =============================================================================
# Each entry maps parameter name -> {"type": ..., "required": bool,
# "min": ..., "max": ..., "allowed": [...]}

STUDY_TYPE_PARAMETER_SCHEMAS: Dict[ETAPStudyType, Dict[str, Dict[str, Any]]] = {
    ETAPStudyType.LOAD_FLOW: {
        "method": {
            "type": "string",
            "allowed": ["newton_raphson", "fast_decoupled", "gauss_seidel"],
            "required": False,
        },
        "max_iterations": {"type": "integer", "min": 1, "max": 1000, "required": False},
        "tolerance": {"type": "numeric", "min": 1e-12, "max": 1.0, "required": False},
        "acceleration_factor": {"type": "numeric", "min": 0.1, "max": 5.0, "required": False},
    },
    ETAPStudyType.SHORT_CIRCUIT: {
        "fault_type": {
            "type": "string",
            "allowed": ["ThreePhase", "LineToGround", "LineToLine", "DoubleLineToGround"],
            "required": False,
        },
        "standard": {"type": "string", "allowed": ["iec60909", "ansi"], "required": False},
        "prefault_voltage_pu": {"type": "numeric", "min": 0.5, "max": 1.5, "required": False},
    },
    ETAPStudyType.ARC_FLASH: {
        "working_distance_mm": {"type": "numeric", "min": 50.0, "max": 50000.0, "required": False},
        "electrode_config": {
            "type": "string",
            "allowed": ["VCB", "VCBB", "HCB", "VOA", "HOA"],
            "required": False,
        },
        "enclosure_type": {"type": "string", "allowed": ["open", "box"], "required": False},
        "arc_duration_sec": {"type": "numeric", "min": 0.001, "max": 100.0, "required": False},
    },
    ETAPStudyType.HARMONIC_ANALYSIS: {
        "max_harmonic_order": {"type": "integer", "min": 2, "max": 100, "required": False},
        "standard": {"type": "string", "allowed": ["ieee519", "iec61000"], "required": False},
        "include_interharmonics": {"type": "boolean", "required": False},
    },
    ETAPStudyType.OPTIMAL_POWER_FLOW: {
        "method": {"type": "string", "allowed": ["dc", "ac"], "required": False},
        "objective": {
            "type": "string",
            "allowed": ["min_cost", "min_losses", "min_violations"],
            "required": False,
        },
        "include_reactive": {"type": "boolean", "required": False},
    },
    ETAPStudyType.MOTOR_STARTING: {
        "starting_method": {
            "type": "string",
            "allowed": ["across_the_line", "soft_starter", "vfd", "autotransformer"],
            "required": False,
        },
        "voltage_dip_limit_percent": {
            "type": "numeric",
            "min": 0.0,
            "max": 100.0,
            "required": False,
        },
    },
    ETAPStudyType.MOTOR_ACCELERATION: {
        "acceleration_method": {
            "type": "string",
            "allowed": ["full_voltage", "reduced_voltage"],
            "required": False,
        },
        "load_model": {
            "type": "string",
            "allowed": ["constant_torque", "quadratic", "linear"],
            "required": False,
        },
    },
    ETAPStudyType.PROTECTION_COORDINATION: {
        "curve_type": {
            "type": "string",
            "allowed": [
                "standard_inverse",
                "very_inverse",
                "extremely_inverse",
                "long_time_inverse",
            ],
            "required": False,
        },
        "tms_min": {"type": "numeric", "min": 0.025, "max": 10.0, "required": False},
        "tms_max": {"type": "numeric", "min": 0.025, "max": 10.0, "required": False},
    },
    ETAPStudyType.TRANSIENT_STABILITY: {
        "simulation_duration_sec": {
            "type": "numeric",
            "min": 0.1,
            "max": 3600.0,
            "required": False,
        },
        "time_step_sec": {"type": "numeric", "min": 0.0001, "max": 0.1, "required": False},
        "event_list": {"type": "list", "required": False},
    },
    ETAPStudyType.CABLE_AMACITY: {
        "installation_method": {
            "type": "string",
            "allowed": ["underground", "conduit", "cable_tray", "direct_burial"],
            "required": False,
        },
        "ambient_temperature_c": {"type": "numeric", "min": -40.0, "max": 80.0, "required": False},
        "voltage_kv": {"type": "numeric", "min": 0.1, "max": 500.0, "required": False},
    },
    ETAPStudyType.GROUND_GRID: {
        "soil_resistivity_ohm_m": {
            "type": "numeric",
            "min": 0.1,
            "max": 10000.0,
            "required": False,
        },
        "surface_layer_thickness_m": {
            "type": "numeric",
            "min": 0.0,
            "max": 10.0,
            "required": False,
        },
    },
    ETAPStudyType.RELIABILITY: {
        "analysis_type": {
            "type": "string",
            "allowed": ["failure_modes", "reliability_indices", "cost_analysis"],
            "required": False,
        },
        "time_period_years": {"type": "integer", "min": 1, "max": 50, "required": False},
    },
}


@dataclass
class ETAPResult:
    """Container for ETAP study results."""

    study_type: str
    success: bool
    data: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
    timestamp: float


class ETAPProject:
    """Represents an open ETAP project."""

    def __init__(self, com_project, file_path: str, com_timeout: int = 300):
        self._com_project = com_project
        self.file_path = file_path
        self.is_open = True
        self._com_timeout = com_timeout

    def run_study(self, study_type: ETAPStudyType, **kwargs) -> ETAPResult:
        """
        Run a specific study in the ETAP project.

        Parameters:
        study_type: Type of study to run
        **kwargs: Study-specific parameters

        Returns:
        ETAPResult with study outcomes
        """
        if not self.is_open:
            raise RuntimeError("Project is not open")
        if not isinstance(study_type, ETAPStudyType):
            raise ValueError(f"study_type must be ETAPStudyType, got {type(study_type).__name__}")

        # Strict schema validation per study_type (reject unknown keys).
        ETAPAutomation._validate_study_parameters(study_type, kwargs)

        start_time = time.time()
        warnings: List[str] = []
        errors: List[str] = []

        try:
            if study_type == ETAPStudyType.LOAD_FLOW:
                result = self._run_load_flow(**kwargs)
            elif study_type == ETAPStudyType.SHORT_CIRCUIT:
                result = self._run_short_circuit(**kwargs)
            elif study_type == ETAPStudyType.ARC_FLASH:
                result = self._run_arc_flash(**kwargs)
            elif study_type == ETAPStudyType.HARMONIC_ANALYSIS:
                result = self._run_harmonic_analysis(**kwargs)
            elif study_type == ETAPStudyType.OPTIMAL_POWER_FLOW:
                result = self._run_optimal_power_flow(**kwargs)
            elif study_type in (ETAPStudyType.MOTOR_STARTING, ETAPStudyType.MOTOR_ACCELERATION):
                result = self._run_motor_starting(**kwargs)
            elif study_type == ETAPStudyType.TRANSIENT_STABILITY:
                result = self._run_transient_stability(**kwargs)
            elif study_type == ETAPStudyType.CABLE_AMACITY:
                result = self._run_cable_ampacity(**kwargs)
            elif study_type == ETAPStudyType.GROUND_GRID:
                result = self._run_ground_grid(**kwargs)
            elif study_type == ETAPStudyType.RELIABILITY:
                result = self._run_reliability(**kwargs)
            elif study_type == ETAPStudyType.PROTECTION_COORDINATION:
                result = self._run_protection_coordination(**kwargs)
            else:
                # Graceful fallback for future enum members without handlers
                return ETAPResult(
                    study_type=study_type.value,
                    success=False,
                    data={},
                    warnings=[],
                    errors=[f"Study type {study_type.value} not yet implemented via COM"],
                    timestamp=start_time,
                )

            return ETAPResult(
                study_type=study_type.value,
                success=True,
                data=result,
                warnings=warnings,
                errors=errors,
                timestamp=start_time,
            )

        except Exception as e:
            errors.append(str(e))
            logger.error(f"Study {study_type.value} failed: {e}")
            return ETAPResult(
                study_type=study_type.value,
                success=False,
                data={},
                warnings=warnings,
                errors=errors,
                timestamp=start_time,
            )

    def _run_load_flow(self, **kwargs) -> Dict[str, Any]:
        """Run load flow study (params already validated by run_study)."""
        try:
            lf_module = self._com_project.LoadFlow
            if lf_module:
                lf_module.Calculate()

                buses = {}
                for bus in self._com_project.Buses:
                    bus_id = getattr(bus, "ID", "")
                    ETAPAutomation._validate_bus_id(bus_id)
                    buses[bus_id] = {
                        "voltage_magnitude": getattr(bus, "VoltageMag", 0.0),
                        "voltage_angle": getattr(bus, "VoltageAng", 0.0),
                        "active_power": getattr(bus, "PMW", 0.0),
                        "reactive_power": getattr(bus, "QMVAR", 0.0),
                    }

                branches = {}
                for branch in self._com_project.Branches:
                    branch_id = getattr(branch, "ID", "")
                    branches[branch_id] = {
                        "active_power_from": getattr(branch, "PFrom", 0.0),
                        "reactive_power_from": getattr(branch, "QFrom", 0.0),
                        "active_power_to": getattr(branch, "PTo", 0.0),
                        "reactive_power_to": getattr(branch, "QTo", 0.0),
                        "current": getattr(branch, "Current", 0.0),
                    }

                result = {
                    "converged": True,
                    "buses": buses,
                    "branches": branches,
                    "iterations": getattr(lf_module, "Iterations", 0),
                }
                ETAPAutomation._check_result_size(result)
                return result
            else:
                raise RuntimeError("Load Flow module not available")

        except pythoncom.com_error as e:
            raise RuntimeError(
                f"COM error during load flow execution (timeout={self._com_timeout}s): {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Load flow execution failed: {e}") from e

    def _run_short_circuit(self, **kwargs) -> Dict[str, Any]:
        """Run short circuit study (params already validated by run_study)."""
        fault_type = kwargs.get("fault_type", "ThreePhase")
        if fault_type not in VALID_FAULT_TYPES:
            raise ValueError(
                f"Invalid fault_type '{fault_type}'. Must be one of {sorted(VALID_FAULT_TYPES)}"
            )
        try:
            sc_module = self._com_project.ShortCircuit
            if sc_module:
                sc_module.FaultType = fault_type
                sc_module.Calculate()

                faults = {}
                for bus in self._com_project.Buses:
                    bus_id = getattr(bus, "ID", "")
                    ETAPAutomation._validate_bus_id(bus_id)
                    faults[bus_id] = {
                        "three_phase_ka": getattr(bus, "I3PhaseKA", 0.0),
                        "line_to_ground_ka": getattr(bus, "ILGKA", 0.0),
                        "line_to_line_ka": getattr(bus, "IllKA", 0.0),
                        "double_line_to_ground_ka": getattr(bus, "IDLGKA", 0.0),
                    }

                result = {"fault_currents": faults, "fault_type": fault_type}
                ETAPAutomation._check_result_size(result)
                return result
            else:
                raise RuntimeError("Short Circuit module not available")

        except pythoncom.com_error as e:
            raise RuntimeError(
                f"COM error during short circuit execution (timeout={self._com_timeout}s): {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Short circuit execution failed: {e}") from e

    def _run_arc_flash(self, **kwargs) -> Dict[str, Any]:
        """Run arc flash study (params already validated by run_study)."""
        working_distance = kwargs.get("working_distance_mm", 610)
        working_distance = ETAPAutomation._validate_input(
            working_distance, "numeric", min_val=WORKING_DISTANCE_MIN, max_val=WORKING_DISTANCE_MAX
        )
        try:
            af_module = self._com_project.ArcFlash
            if af_module:
                af_module.WorkingDistance = working_distance / 1000

                af_module.Calculate()

                equipment = {}
                for equip in self._com_project.Equipment:
                    equip_id = getattr(equip, "ID", "")
                    equipment[equip_id] = {
                        "incident_energy_cal_cm2": getattr(equip, "IncidentEnergy", 0),
                        "arc_flash_boundary_mm": getattr(equip, "ArcFlashBoundary", 0) * 1000,
                        "ppe_level": getattr(equip, "PPELevel", "Unknown"),
                        "arc_duration_sec": getattr(equip, "ArcDuration", 0),
                    }

                result = {"equipment_results": equipment, "standard": "IEEE 1584-2018"}
                ETAPAutomation._check_result_size(result)
                return result
            else:
                raise RuntimeError("Arc Flash module not available")

        except pythoncom.com_error as e:
            raise RuntimeError(
                f"COM error during arc flash execution (timeout={self._com_timeout}s): {e}"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Arc flash execution failed: {e}") from e

    def _run_harmonic_analysis(self, **kwargs) -> Dict[str, Any]:
        """Run harmonic analysis study via ETAP COM.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        buses = {}
        try:
            harm_module = getattr(self._com_project, "HarmonicAnalysis", None)
            if harm_module is None or not hasattr(harm_module, "Calculate"):
                raise RuntimeError("HarmonicAnalysis module not available in ETAP project")
            harm_module.Calculate()
            for bus in self._com_project.Buses:
                bus_id = str(getattr(bus, "ID", ""))
                if bus_id:
                    ETAPAutomation._validate_bus_id(bus_id)
                    buses[bus_id] = {
                        "voltage_thd_percent": float(getattr(bus, "VTHD", 0.0)),
                        "current_thd_percent": float(getattr(bus, "ITHD", 0.0)),
                        "fundamental_voltage_mag": float(getattr(bus, "VoltageMag", 1.0)),
                        "dominant_harmonic_order": int(getattr(bus, "DominantHarmonic", 5)),
                    }
        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during harmonic analysis: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Harmonic analysis execution failed: {e}") from e

        if not buses:
            raise RuntimeError("Harmonic analysis returned no bus results from ETAP")

        result = {
            "converged": True,
            "buses": buses,
            "standard": "IEEE 519-2014",
            "total_harmonic_distortion_limit_percent": 5.0,
        }
        ETAPAutomation._check_result_size(result)
        return result

    def _run_optimal_power_flow(self, **kwargs) -> Dict[str, Any]:
        """Run optimal power flow study via ETAP COM.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        generators = {}
        try:
            opf_module = getattr(self._com_project, "OptimalPowerFlow", None)
            if opf_module is None or not hasattr(opf_module, "Calculate"):
                raise RuntimeError("OptimalPowerFlow module not available in ETAP project")
            opf_module.Calculate()
            for gen in getattr(self._com_project, "Generators", []):
                gen_id = str(getattr(gen, "ID", ""))
                if gen_id:
                    generators[gen_id] = {
                        "active_power_mw": float(getattr(gen, "PMW", 0.0)),
                        "reactive_power_mvar": float(getattr(gen, "QMVAR", 0.0)),
                        "cost_per_hour": float(getattr(gen, "Cost", 0.0)),
                    }
        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during optimal power flow: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"OPF execution failed: {e}") from e

        if not generators:
            raise RuntimeError("OPF returned no generator results from ETAP")

        total_gen = sum(g["active_power_mw"] for g in generators.values())
        total_cost = sum(g["cost_per_hour"] for g in generators.values())
        total_loss = float(getattr(opf_module, "TotalLosses", 0.0))

        result = {
            "converged": True,
            "generators": generators,
            "total_system_loss_mw": total_loss,
            "total_generation_cost_per_hour": total_cost,
            "total_generation_mw": total_gen,
            "optimization_objective": str(getattr(opf_module, "Objective", "Minimize Cost")),
        }
        ETAPAutomation._check_result_size(result)
        return result

    def _run_motor_starting(self, **kwargs) -> Dict[str, Any]:
        """Run motor starting / acceleration study via ETAP COM.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        motors = {}
        try:
            ms_module = getattr(self._com_project, "MotorStarting", None)
            if ms_module is None:
                ms_module = getattr(self._com_project, "MotorAcceleration", None)
            if ms_module is None or not hasattr(ms_module, "Calculate"):
                raise RuntimeError("MotorStarting module not available in ETAP project")
            ms_module.Calculate()
            for motor in getattr(self._com_project, "Motors", []):
                motor_id = str(getattr(motor, "ID", ""))
                if motor_id:
                    motors[motor_id] = {
                        "starting_current_multiplier": float(
                            getattr(motor, "StartingCurrentMult", 0.0)
                        ),
                        "acceleration_time_sec": float(getattr(motor, "AccelTime", 0.0)),
                        "min_voltage_during_start_pu": float(getattr(motor, "MinVoltagePU", 0.0)),
                        "speed_at_end_of_start_percent": float(getattr(motor, "SpeedPercent", 0.0)),
                    }
        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during motor starting analysis: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Motor starting execution failed: {e}") from e

        if not motors:
            raise RuntimeError("Motor starting returned no motor results from ETAP")

        max_dip = min(m["min_voltage_during_start_pu"] for m in motors.values()) if motors else 1.0
        max_recovery = max(m["acceleration_time_sec"] for m in motors.values()) if motors else 0.0

        result = {
            "converged": True,
            "motors": motors,
            "voltage_dip_profile": {
                "max_dip_percent": round((1.0 - max_dip) * 100.0, 1),
                "recovery_time_sec": round(max_recovery, 2),
            },
            "starting_method": str(getattr(ms_module, "StartingMethod", "Across-the-Line")),
        }
        ETAPAutomation._check_result_size(result)
        return result

    def _run_transient_stability(self, **kwargs) -> Dict[str, Any]:
        """
        Run transient stability study via ETAP COM.

        Extracts rotor angle, speed, and voltage trajectories from the
        ETAP Transient Stability module.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        duration = float(kwargs.get("simulation_duration_sec", 5.0))
        time_step = float(kwargs.get("time_step_sec", 0.01))
        max_points = max(1, min(int(duration / time_step), 1000))

        generators: Dict[str, Any] = {}
        try:
            ts_module = getattr(self._com_project, "TransientStability", None)
            if ts_module is None or not hasattr(ts_module, "Calculate"):
                raise RuntimeError("TransientStability module not available in ETAP project")
            ts_module.Calculate()
            for gen in getattr(self._com_project, "Generators", []):
                gen_id = str(getattr(gen, "ID", ""))
                if not gen_id:
                    continue
                # Read trajectories from COM module
                raw_angles = getattr(gen, "RotorAngleTrajectory", None)
                raw_times = getattr(gen, "TimeTrajectory", None)
                if raw_angles and raw_times:
                    angles = [float(a) for a in raw_angles[:max_points]]
                    times = [float(t) for t in raw_times[:max_points]]
                else:
                    angles = []
                    times = []
                generators[gen_id] = {
                    "rotor_angle_deg": angles,
                    "time_sec": times,
                    "max_angle_deg": max(angles) if angles else 0.0,
                    "critical_clearing_time_sec": float(getattr(gen, "CriticalClearingTime", 0.0)),
                }
        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during transient stability: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Transient stability execution failed: {e}") from e

        if not generators:
            raise RuntimeError("Transient stability returned no generator results from ETAP")

        result = {
            "converged": True,
            "generators": generators,
            "simulation_duration_sec": duration,
            "time_step_sec": time_step,
            "standard": "IEEE 421 / IEC 60909",
            "stable": all(g["max_angle_deg"] < 180.0 for g in generators.values()),
        }
        ETAPAutomation._check_result_size(result)
        return result

    def _run_cable_ampacity(self, **kwargs) -> Dict[str, Any]:
        """
        Run cable ampacity (current-carrying capacity) study via ETAP COM.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        installation = str(kwargs.get("installation_method", "conduit"))
        ambient_c = float(kwargs.get("ambient_temperature_c", 30.0))

        cables: Dict[str, Any] = {}
        try:
            cable_module = getattr(self._com_project, "Cables", None)
            if cable_module is None:
                raise RuntimeError("Cables module not available in ETAP project")
            for cable in cable_module:
                cable_id = str(getattr(cable, "ID", ""))
                if cable_id:
                    base_rating = float(getattr(cable, "Ampacity", 0.0))
                    derated = float(getattr(cable, "DeratedAmpacity", base_rating))
                    cables[cable_id] = {
                        "base_ampacity_a": base_rating,
                        "installation_method": installation,
                        "ambient_temperature_c": ambient_c,
                        "derated_ampacity_a": round(derated, 2),
                        "voltage_kv": float(getattr(cable, "KV", 0.0)),
                    }
        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during cable ampacity study: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Cable ampacity execution failed: {e}") from e

        if not cables:
            raise RuntimeError("Cable ampacity returned no cable results from ETAP")

        result = {
            "converged": True,
            "cables": cables,
            "standard": "IEC 60287 / NEC Article 310",
            "installation_method": installation,
        }
        ETAPAutomation._check_result_size(result)
        return result

    def _run_ground_grid(self, **kwargs) -> Dict[str, Any]:
        """
        Run ground grid analysis per IEEE 80 via ETAP COM.

        Reads grid geometry, fault current, and soil model from the ETAP
        project and returns calculated touch/step voltages and compliance.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        try:
            gg_module = getattr(self._com_project, "GroundGrid", None)
            if gg_module is None or not hasattr(gg_module, "Calculate"):
                raise RuntimeError("GroundGrid module not available in ETAP project")
            gg_module.Calculate()

            result = {
                "converged": True,
                "soil_resistivity_ohm_m": float(getattr(gg_module, "SoilResistivity", 0.0)),
                "surface_layer_thickness_m": float(getattr(gg_module, "SurfaceThickness", 0.0)),
                "grid_resistance_ohm": float(getattr(gg_module, "GridResistance", 0.0)),
                "mesh_voltage_v": float(getattr(gg_module, "MeshVoltage", 0.0)),
                "step_voltage_v": float(getattr(gg_module, "StepVoltage", 0.0)),
                "grid_potential_rise_v": float(getattr(gg_module, "GPR", 0.0)),
                "rod_count": int(getattr(gg_module, "RodCount", 0)),
                "standard": "IEEE 80-2013",
                "compliance": {
                    "touch_voltage_limit_v": float(getattr(gg_module, "TouchVoltageLimit", 0.0)),
                    "step_voltage_limit_v": float(getattr(gg_module, "StepVoltageLimit", 0.0)),
                    "touch_ok": bool(getattr(gg_module, "TouchCompliant", False)),
                    "step_ok": bool(getattr(gg_module, "StepCompliant", False)),
                },
            }
        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during ground grid analysis: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Ground grid execution failed: {e}") from e

        ETAPAutomation._check_result_size(result)
        return result

    def _run_reliability(self, **kwargs) -> Dict[str, Any]:
        """
        Run reliability analysis (SAIDI / SAIFI / CAIDI / ASAI) via ETAP COM.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        period_years = int(kwargs.get("time_period_years", 1))
        analysis_type = str(kwargs.get("analysis_type", "reliability_indices"))

        try:
            rel_module = getattr(self._com_project, "Reliability", None)
            if rel_module is None or not hasattr(rel_module, "Calculate"):
                raise RuntimeError("Reliability module not available in ETAP project")
            rel_module.Calculate()

            customers_served = int(getattr(rel_module, "CustomersServed", 0))
            sustained_outages = int(getattr(rel_module, "SustainedOutages", 0))
            momentary_outages = int(getattr(rel_module, "MomentaryOutages", 0))
            total_outage_hours = float(getattr(rel_module, "TotalOutageHours", 0.0))

            if customers_served <= 0:
                raise RuntimeError("Reliability analysis returned zero customers served")

            saifi = sustained_outages / customers_served
            saidi = total_outage_hours / customers_served
            caidi = saidi / saifi if saifi > 0 else 0.0
            asai = 1.0 - (total_outage_hours / (period_years * 8760.0))
            maifi = momentary_outages / customers_served

        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during reliability analysis: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Reliability analysis execution failed: {e}") from e

        result = {
            "converged": True,
            "analysis_type": analysis_type,
            "time_period_years": period_years,
            "customers_served": customers_served,
            "sustained_outages": sustained_outages,
            "momentary_outages": momentary_outages,
            "total_outage_hours": total_outage_hours,
            "indices": {
                "SAIFI": round(saifi, 4),
                "SAIDI": round(saidi, 4),
                "CAIDI": round(caidi, 4),
                "ASAI": round(asai, 6),
                "MAIFI": round(maifi, 4),
            },
            "standard": "IEEE 1366-2012",
        }
        ETAPAutomation._check_result_size(result)
        return result

    def _run_protection_coordination(self, **kwargs) -> Dict[str, Any]:
        """
        Run protection coordination study via ETAP COM.

        Raises RuntimeError if COM module is unavailable or returns no data.
        """
        curve_type = str(kwargs.get("curve_type", "standard_inverse"))
        tms_min = float(kwargs.get("tms_min", 0.025))
        tms_max = float(kwargs.get("tms_max", 10.0))

        pairs: Dict[str, Any] = {}
        try:
            prot_module = getattr(self._com_project, "ProtectionCoordination", None)
            if prot_module is None or not hasattr(prot_module, "Calculate"):
                raise RuntimeError("ProtectionCoordination module not available in ETAP project")
            prot_module.Calculate()

            relay_iter = getattr(self._com_project, "Relays", None)
            if relay_iter is None:
                raise RuntimeError("No relays found in ETAP project")

            for relay in relay_iter:
                pid = str(getattr(relay, "ID", ""))
                if not pid:
                    continue
                relay_results = []
                coord_data = getattr(relay, "CoordinationResults", None)
                if coord_data:
                    for entry in coord_data:
                        relay_results.append(
                            {
                                "fault_current_pu": float(getattr(entry, "FaultCurrent", 0.0)),
                                "primary_trip_time_sec": float(getattr(entry, "PrimaryTime", 0.0)),
                                "backup_trip_time_sec": float(getattr(entry, "BackupTime", 0.0)),
                                "cti_margin_sec": float(getattr(entry, "CTI", 0.0)),
                                "coordinated": bool(getattr(entry, "Coordinated", False)),
                            }
                        )
                pairs[pid] = {
                    "curve_type": str(getattr(relay, "CurveType", curve_type)),
                    "tms": float(getattr(relay, "TMS", 0.0)),
                    "results": relay_results,
                    "all_coordinated": all(r["coordinated"] for r in relay_results)
                    if relay_results
                    else False,
                }
        except (pythoncom.com_error, AttributeError) as e:
            raise RuntimeError(f"COM error during protection coordination: {e}") from e
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Protection coordination execution failed: {e}") from e

        if not pairs:
            raise RuntimeError("Protection coordination returned no relay results from ETAP")

        result = {
            "converged": True,
            "relay_pairs": pairs,
            "standard": "IEC 60255-151",
            "curve_type": curve_type,
            "tms_min": tms_min,
            "tms_max": tms_max,
        }
        ETAPAutomation._check_result_size(result)
        return result

    def get_bus_data(self, bus_id: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific bus."""
        ETAPAutomation._validate_bus_id(bus_id)
        try:
            bus = self._com_project.Buses.Item(bus_id)
            if bus:
                return {
                    "id": bus.ID,
                    "name": bus.Name,
                    "voltage_kv": bus.KV,
                    "voltage_mag_pu": bus.VoltageMag,
                    "voltage_ang_deg": bus.VoltageAng,
                    "type": bus.BusType,
                }
        except pythoncom.com_error as e:
            logger.warning(f"COM error retrieving bus {bus_id} (timeout={self._com_timeout}s): {e}")
        except Exception as e:
            logger.warning(f"Could not retrieve bus {bus_id}: {e}")
        return None

    def get_all_buses(self) -> List[Dict[str, Any]]:
        """Get data for all buses."""
        buses = []
        try:
            for bus in self._com_project.Buses:
                bus_id = getattr(bus, "ID", "")
                if bus_id:
                    data = self.get_bus_data(bus_id)
                    if data:
                        buses.append(data)
        except pythoncom.com_error as e:
            logger.error(f"COM error retrieving buses (timeout={self._com_timeout}s): {e}")
        except Exception as e:
            logger.error(f"Error retrieving buses: {e}")
        return buses

    def save(self, file_path: Optional[str] = None) -> bool:
        """Save the project."""
        try:
            path = file_path or self.file_path
            if path is not None and len(str(path)) > MAX_PROJECT_PATH_LENGTH:
                raise ValueError(
                    f"File path length {len(str(path))} exceeds maximum {MAX_PROJECT_PATH_LENGTH}"
                )
            self._com_project.SaveAs(path)
            self.file_path = path
            return True
        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            return False

    def close(self) -> bool:
        """Close the project."""
        try:
            self._com_project.Close()
            self.is_open = False
            return True
        except Exception as e:
            logger.error(f"Failed to close project: {e}")
            return False


class ETAPAutomation:
    """
    Main ETAP automation interface.

    Provides methods to:
    - Launch ETAP application
    - Open/create projects
    - Execute studies
    - Extract results
    - Automate workflows

    Includes built-in input validation for all user-facing parameters,
    size limits on results, and configurable COM call timeouts.
    """

    def __init__(self, visible: bool = True, com_timeout_seconds: int = 300):
        """
        Initialize ETAP automation.

        Parameters:
        visible: Whether to show ETAP GUI (True) or run hidden (False)
        com_timeout_seconds: Maximum time in seconds to wait for COM calls before timing out
        """
        if not WIN32_AVAILABLE:
            raise ImportError("pywin32 is required for ETAP automation on Windows")

        self._com_app = None
        self._projects: Dict[str, ETAPProject] = {}
        self.visible = visible
        self.com_timeout_seconds = com_timeout_seconds
        self.is_running = False
        self._allowed_project_dirs: List[str] = []

    # -------------------------------------------------------------------------
    # Input validation helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _validate_input(
        value,
        value_type: str,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
        max_length: Optional[int] = None,
    ) -> Union[int, float, str, bool]:
        """
        Generic input validator.

        Parameters:
        value: Value to validate
        value_type: One of 'numeric', 'integer', 'string', 'boolean'
        min_val: Minimum allowed value (numeric/integer)
        max_val: Maximum allowed value (numeric/integer)
        max_length: Maximum string length (string only)

        Returns:
        The validated value (possibly coerced to the expected type)

        Raises:
        ValueError if validation fails
        """
        if value_type == "numeric":
            try:
                num = float(value)
            except (ValueError, TypeError) as err:
                raise ValueError(f"Expected numeric value, got {type(value).__name__}") from err
            if not (MIN_NUMERIC_VALUE <= num <= MAX_NUMERIC_VALUE):
                raise ValueError(
                    f"Value {num} outside system range [{MIN_NUMERIC_VALUE}, {MAX_NUMERIC_VALUE}]"
                )
            if min_val is not None and num < min_val:
                raise ValueError(f"Value {num} below minimum {min_val}")
            if max_val is not None and num > max_val:
                raise ValueError(f"Value {num} above maximum {max_val}")
            return num

        elif value_type == "integer":
            try:
                val = int(value)
            except (ValueError, TypeError) as err:
                raise ValueError(f"Expected integer value, got {type(value).__name__}") from err
            if min_val is not None and val < min_val:
                raise ValueError(f"Value {val} below minimum {min_val}")
            if max_val is not None and val > max_val:
                raise ValueError(f"Value {val} above maximum {max_val}")
            return val

        elif value_type == "string":
            if not isinstance(value, str):
                raise ValueError(f"Expected string value, got {type(value).__name__}")
            limit = max_length if max_length is not None else MAX_STRING_INPUT_LENGTH
            if len(value) > limit:
                raise ValueError(f"String length {len(value)} exceeds maximum {limit}")
            return value

        elif value_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"Expected boolean value, got {type(value).__name__}")
            return value

        else:
            raise ValueError(f"Unknown validation type: {value_type}")

    @staticmethod
    def _sanitize_string_input(input_str: str, max_length: int = 1000) -> str:
        """
        Sanitize string inputs.

        Removes null bytes and strips HTML tags. Truncates to max_length.

        Parameters:
        input_str: Raw input string
        max_length: Maximum allowed length after sanitization

        Returns:
        Sanitized string
        """
        if not isinstance(input_str, str):
            raise ValueError(f"Expected string, got {type(input_str).__name__}")
        sanitized = input_str.replace("\x00", "")
        sanitized = re.sub(r"<[^>]*>", "", sanitized)
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized

    @staticmethod
    def _validate_study_parameters(
        study_type: ETAPStudyType, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate study parameters against the per-study-type schema.

        Rejects unknown/unexpected parameter keys and validates types and
        ranges against the predefined schema for the study type.

        Parameters:
        study_type: The ETAP study type defining the allowed parameter schema
        params: Study parameters dict to validate

        Returns:
        The validated parameters dict

        Raises:
        ValueError if unknown keys are present or values fail validation
        """
        if not isinstance(params, dict):
            raise ValueError(f"Study parameters must be a dict, got {type(params).__name__}")

        if not isinstance(study_type, ETAPStudyType):
            raise ValueError(f"study_type must be ETAPStudyType, got {type(study_type).__name__}")

        schema = STUDY_TYPE_PARAMETER_SCHEMAS.get(study_type, {})

        for key in params:
            if not isinstance(key, str):
                raise ValueError(
                    f"Study parameter key must be string, got {type(key).__name__} for key={key}"
                )
            if len(key) > 256:
                raise ValueError(f"Study parameter key too long ({len(key)} chars): {key[:50]}...")

            # Reject unknown/unexpected parameter keys
            if key not in schema:
                allowed = sorted(schema.keys()) if schema else ["(none)"]
                raise ValueError(
                    f"Unknown parameter '{key}' for study type {study_type.value}. "
                    f"Allowed parameters: {allowed}"
                )

            rule = schema[key]
            value = params[key]
            expected_type = rule.get("type", "string")

            # Type validation
            if expected_type == "numeric":
                try:
                    value = float(value)
                except (ValueError, TypeError) as err:
                    raise ValueError(
                        f"Parameter '{key}' must be numeric, got {type(value).__name__}"
                    ) from err
                min_val = rule.get("min")
                max_val = rule.get("max")
                if min_val is not None and value < min_val:
                    raise ValueError(f"Parameter '{key}' value {value} below minimum {min_val}")
                if max_val is not None and value > max_val:
                    raise ValueError(f"Parameter '{key}' value {value} above maximum {max_val}")

            elif expected_type == "integer":
                try:
                    value = int(value)
                except (ValueError, TypeError) as err:
                    raise ValueError(
                        f"Parameter '{key}' must be integer, got {type(value).__name__}"
                    ) from err
                min_val = rule.get("min")
                max_val = rule.get("max")
                if min_val is not None and value < min_val:
                    raise ValueError(f"Parameter '{key}' value {value} below minimum {min_val}")
                if max_val is not None and value > max_val:
                    raise ValueError(f"Parameter '{key}' value {value} above maximum {max_val}")

            elif expected_type == "string":
                if not isinstance(value, str):
                    raise ValueError(
                        f"Parameter '{key}' must be string, got {type(value).__name__}"
                    )
                allowed_vals = rule.get("allowed")
                if allowed_vals is not None and value not in allowed_vals:
                    raise ValueError(
                        f"Parameter '{key}' value '{value}' not in allowed: {allowed_vals}"
                    )

            elif expected_type == "boolean":
                if not isinstance(value, bool):
                    raise ValueError(
                        f"Parameter '{key}' must be boolean, got {type(value).__name__}"
                    )

            elif expected_type == "list":
                if not isinstance(value, list):
                    raise ValueError(
                        f"Parameter '{key}' must be a list, got {type(value).__name__}"
                    )

            else:
                raise ValueError(
                    f"Internal error: unknown schema type '{expected_type}' for parameter '{key}'"
                )

        # Check required parameters
        for key, rule in schema.items():
            if rule.get("required", False) and key not in params:
                raise ValueError(
                    f"Required parameter '{key}' missing for study type {study_type.value}"
                )

        return params

    @staticmethod
    def _sanitize_project_name(name: str) -> str:
        """
        Sanitize project name to alphanumeric characters and underscores only.

        Parameters:
        name: Raw project name

        Returns:
        Sanitized project name safe for file system and ETAP
        """
        sanitized = ETAPAutomation._sanitize_string_input(name, max_length=256)
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", sanitized)
        if not sanitized:
            raise ValueError("Project name is empty after sanitization")
        return sanitized

    @staticmethod
    def _validate_bus_id(bus_id: str) -> str:
        """
        Validate bus ID format.

        Parameters:
        bus_id: Bus identifier string

        Returns:
        Validated bus ID

        Raises:
        ValueError if bus ID is invalid
        """
        if not isinstance(bus_id, str) or not bus_id:
            raise ValueError("Bus ID must be a non-empty string")
        if len(bus_id) > MAX_BUS_NAME_LENGTH:
            raise ValueError(f"Bus ID length {len(bus_id)} exceeds maximum {MAX_BUS_NAME_LENGTH}")
        return bus_id

    @staticmethod
    def _check_result_size(
        result_dict: Dict[str, Any], max_entries: int = MAX_RESULT_ENTRIES
    ) -> Dict[str, Any]:
        """
        Check that a result dictionary does not exceed maximum entry count.

        Counts leaf elements in nested dicts and lists.

        Parameters:
        result_dict: The result dictionary to check
        max_entries: Maximum allowed entry count

        Returns:
        The result dict if within limits

        Raises:
        ValueError if the result exceeds max_entries
        """
        if not isinstance(result_dict, dict):
            raise TypeError(f"Expected dict, got {type(result_dict).__name__}")
        total = 0
        for _key, value in result_dict.items():
            if isinstance(value, dict):
                total += len(value)
            elif isinstance(value, (list, tuple)):
                total += len(value)
            else:
                total += 1
            if total > max_entries:
                raise ValueError(f"Result size ({total} entries) exceeds maximum ({max_entries})")
        return result_dict

    # -------------------------------------------------------------------------
    # Project path security
    # -------------------------------------------------------------------------

    def add_allowed_project_directory(self, directory: str) -> None:
        """Add a directory to the allowed project path list."""
        resolved = pathlib.Path(directory).resolve()
        self._allowed_project_dirs.append(str(resolved))

    def _validate_project_path(self, file_path: str) -> bool:
        """
        Validate that a project path is within allowed directories.

        Prevents path traversal and SMB relay attacks.
        Validates path length against configured maximum.
        """
        if not file_path or not isinstance(file_path, str):
            logger.warning(f"Invalid project path type or empty: {file_path}")
            return False

        if len(file_path) > MAX_PROJECT_PATH_LENGTH:
            logger.warning(
                f"Project path length {len(file_path)} exceeds maximum {MAX_PROJECT_PATH_LENGTH}"
            )
            return False

        if not file_path.endswith(".edb"):
            logger.warning(f"Invalid project file extension: {file_path}")
            return False

        try:
            resolved = pathlib.Path(file_path).resolve()
        except (ValueError, RuntimeError):
            logger.warning(f"Invalid path format: {file_path}")
            return False

        # Detect UNC paths cross-platform (Windows \\server\share or //server/share)
        if file_path.startswith("\\\\") or file_path.startswith("//"):
            logger.warning(f"UNC path not allowed (SMB relay risk): {file_path}")
            return False

        if self._allowed_project_dirs:
            is_allowed = any(
                str(resolved).startswith(allowed_dir) for allowed_dir in self._allowed_project_dirs
            )
            if not is_allowed:
                logger.warning(f"Project path outside allowed directories: {file_path}")
                return False

        return True

    # -------------------------------------------------------------------------
    # ETAP lifecycle
    # -------------------------------------------------------------------------

    def launch(self) -> bool:
        """
        Launch ETAP application.

        Returns:
        True if successful
        """
        try:
            self._com_app = win32com.client.Dispatch("ETAP.Application")

            if hasattr(self._com_app, "Visible"):
                self._com_app.Visible = self.visible

            if hasattr(self._com_app, "Timeout"):
                self._com_app.Timeout = self.com_timeout_seconds * 1000

            self.is_running = True
            logger.info("ETAP launched successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to launch ETAP: {e}")
            return False

    def open_project(self, file_path: str) -> Optional[ETAPProject]:
        """
        Open an existing ETAP project.

        Parameters:
        file_path: Path to .edb file

        Returns:
        ETAPProject instance or None if failed
        """
        if not self.is_running:
            raise RuntimeError("ETAP is not running. Call launch() first.")

        if not self._validate_project_path(file_path):
            logger.error(f"Project path validation failed: {file_path}")
            return None

        try:
            com_project = self._com_app.OpenProject(file_path)

            if com_project:
                project = ETAPProject(com_project, file_path, com_timeout=self.com_timeout_seconds)
                self._projects[file_path] = project
                logger.info(f"Opened project: {file_path}")
                return project
            else:
                logger.error(f"Failed to open project: {file_path}")
                return None

        except pythoncom.com_error as e:
            logger.error(
                f"COM error opening project {file_path} (timeout={self.com_timeout_seconds}s): {e}"
            )
            return None
        except Exception as e:
            logger.error(f"Error opening project {file_path}: {e}")
            return None

    def create_project(self, project_name: str = "NewProject") -> Optional[ETAPProject]:
        """
        Create a new ETAP project.

        Parameters:
        project_name: Name for the new project

        Returns:
        ETAPProject instance or None if failed
        """
        if not self.is_running:
            raise RuntimeError("ETAP is not running. Call launch() first.")

        safe_name = self._sanitize_project_name(project_name)

        try:
            com_project = self._com_app.NewProject()

            if com_project:
                if hasattr(com_project, "Name"):
                    com_project.Name = safe_name

                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, f"{safe_name}.edb")
                project = ETAPProject(com_project, temp_path, com_timeout=self.com_timeout_seconds)
                self._projects[temp_path] = project
                logger.info(f"Created new project: {safe_name}")
                return project
            else:
                logger.error("Failed to create new project")
                return None

        except pythoncom.com_error as e:
            logger.error(f"COM error creating project (timeout={self.com_timeout_seconds}s): {e}")
            return None
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return None

    def get_active_project(self) -> Optional[ETAPProject]:
        """Get the currently active project."""
        if not self.is_running:
            return None

        try:
            com_project = self._com_app.ActiveProject
            if com_project:
                for _path, proj in self._projects.items():
                    if proj._com_project == com_project:
                        return proj

                project = ETAPProject(
                    com_project, "ActiveProject", com_timeout=self.com_timeout_seconds
                )
                return project
        except pythoncom.com_error as e:
            logger.error(
                f"COM error getting active project (timeout={self.com_timeout_seconds}s): {e}"
            )
        except Exception as e:
            logger.error(f"Error getting active project: {e}")

        return None

    def close_project(self, file_path: str) -> bool:
        """Close a specific project."""
        if file_path in self._projects:
            project = self._projects[file_path]
            success = project.close()
            if success:
                del self._projects[file_path]
            return success
        return False

    def close_all_projects(self) -> int:
        """Close all open projects. Returns count of closed projects."""
        count = 0
        for path in list(self._projects.keys()):
            if self.close_project(path):
                count += 1
        return count

    def shutdown(self) -> bool:
        """
        Shutdown ETAP application.

        Returns:
        True if successful
        """
        try:
            self.close_all_projects()

            if self._com_app:
                self._com_app.Quit()
                self._com_app = None

            self.is_running = False
            logger.info("ETAP shutdown complete")
            return True

        except pythoncom.com_error as e:
            logger.error(f"COM error shutting down ETAP (timeout={self.com_timeout_seconds}s): {e}")
            return False
        except Exception as e:
            logger.error(f"Error shutting down ETAP: {e}")
            return False

    def get_version(self) -> Optional[str]:
        """Get ETAP version information."""
        if not self.is_running:
            return None

        try:
            if hasattr(self._com_app, "Version"):
                return self._com_app.Version
            return "Unknown"
        except Exception as e:
            logger.error(f"Error getting ETAP version: {e}")
            return None

    def __enter__(self):
        """Context manager entry."""
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


# Convenience function for quick usage
def run_etap_study(project_path: str, study_type: ETAPStudyType, **kwargs) -> ETAPResult:
    """
    Quick function to run a study on a project.

    Parameters:
    project_path: Path to ETAP project file
    study_type: Type of study to run
    **kwargs: Study parameters

    Returns:
    ETAPResult
    """
    with ETAPAutomation(visible=False) as etap:
        project = etap.open_project(project_path)
        if project:
            return project.run_study(study_type, **kwargs)
        else:
            raise RuntimeError(f"Failed to open project: {project_path}")
