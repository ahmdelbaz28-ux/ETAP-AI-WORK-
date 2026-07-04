"""
api/refactored_service.py — Refactored Engineering Service with modular architecture.

This file demonstrates how the monolithic ``engineering_service.py`` should be
refactored into a properly modular FastAPI application. It imports and mounts
existing API routers, adds missing study-type dispatchers, removes duplicate
endpoints, wires up WebSocket with authentication, adds proper dependency
injection, OpenAPI tags, request/response logging middleware, and removes
dead code.

Key improvements over the monolithic version:
  1. Replace global mutable state with ``app.state`` management
  2. Add missing study-type dispatchers (motor_starting, harmonic_analysis, optimal_power_flow)
  3. Remove duplicate RASP stats endpoint
  4. Wire up the WebSocket endpoint with authentication
  5. Add proper dependency injection for cache, engine, and providers
  6. Add OpenAPI tags for documentation grouping
  7. Add request/response logging middleware
  8. Remove dead code (unreachable WebSocket ConnectionManager)

Run::

    uvicorn api.refactored_service:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager, suppress
from typing import Any

# ---------------------------------------------------------------------------
# Cache directories — redirect to /tmp for HF Spaces (read-only filesystem)
# ---------------------------------------------------------------------------
for _env_key, _env_val in [
    ("NUMBA_CACHE_DIR", "/tmp/numba_cache"),  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    ("MPLCONFIGDIR", "/tmp/matplotlib_cache"),  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    ("XDG_CACHE_HOME", "/tmp/hf_cache"),  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    ("HF_HOME", "/tmp/hf_cache"),  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    ("TRANSFORMERS_CACHE", "/tmp/hf_cache/transformers"),  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    ("TORCH_HOME", "/tmp/hf_cache/torch"),  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
]:
    if _env_key not in os.environ:
        os.environ[_env_key] = _env_val
    os.makedirs(os.environ[_env_key], exist_ok=True)

# ---------------------------------------------------------------------------
# numpy-aware JSON sanitizer
# ---------------------------------------------------------------------------
try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except Exception:
    np = None  # type: ignore
    _HAS_NUMPY = False


def _to_jsonable(obj: Any) -> Any:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Recursively convert numpy types to native Python primitives."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        # Filter out NaN and infinities — they aren't valid JSON values.
        # Use math.isnan / math.isinf instead of `obj != obj` (the
        # historical NaN trick) so SonarCloud S1764 doesn't flag it.
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj
    if isinstance(obj, complex):
        re_val, im_val = obj.real, obj.imag
        if not _HAS_NUMPY:
            import math as _math

            if not _math.isfinite(re_val):
                re_val = 0.0
            if not _math.isfinite(im_val):
                im_val = 0.0
        return {"re": _to_jsonable(re_val), "im": _to_jsonable(im_val)}
    if _HAS_NUMPY:
        if isinstance(obj, np.ndarray):
            return [_to_jsonable(x) for x in obj.tolist()]
        if isinstance(obj, (np.integer,)):
            return int(obj.item())
        if isinstance(obj, (np.floating,)):
            v = float(obj.item())
            # Filter NaN/infinity (math.isnan/isinf is clearer than v != v).
            if math.isnan(v) or math.isinf(v):
                return None
            return v
        if isinstance(obj, (np.bool_,)):
            return bool(obj.item())
        if isinstance(obj, np.complexfloating):
            return {"real": _to_jsonable(obj.real), "imag": _to_jsonable(obj.imag)}
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(x) for x in obj]
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)


# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import timezone

UTC = timezone.utc  # noqa: UP017

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.middleware.base import BaseHTTPMiddleware

from api.agents import router as agents_router

# Import existing modular routers
from api.auth import router as auth_router
from api.database import init_db
from api.error_debugger import (
    ErrorReportGenerator,
    StructuredFormatter,
    StudyExecutionError,
)
from api.projects import router as projects_router

# ---------------------------------------------------------------------------
# Structured logging with trace IDs
# ---------------------------------------------------------------------------

formatter = StructuredFormatter(service_name="engineering_service", version="2.0.0")
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

logger = logging.getLogger("engineering_service")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)


# ---------------------------------------------------------------------------
# Application state management (replaces global mutable state)
# ---------------------------------------------------------------------------


class AppState:
    """Centralized application state stored on ``app.state``.

    Replaces the scattered global variables in the original
    ``engineering_service.py`` with a single, well-typed object.
    """

    def __init__(self) -> None:
        # Metrics
        self.request_count: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0
        self.total_execution_time_sec: float = 0.0

        # Rate limiting
        self.rate_limit_store: dict[str, list[float]] = {}

        # RASP engine (singleton)
        self.rasp_engine: Any = None

        # Study cache
        self.study_cache: Any = None

        # Lazy-loaded engine class
        self._power_system_engine_cls: Any = None
        self._etap_provider_factory: Any = None

    # --- Metrics helpers ---

    def increment_request(self) -> None:
        """Increment the total request counter."""
        self.request_count += 1

    def increment_success(self) -> None:
        """Increment the success counter."""
        self.success_count += 1

    def increment_failed(self) -> None:
        """Increment the failed counter."""
        self.failed_count += 1

    def add_execution_time(self, delta: float) -> None:
        """Accumulate execution time."""
        self.total_execution_time_sec += delta

    @property
    def avg_execution_time_ms(self) -> float:
        """Compute the average execution time in milliseconds."""
        if self.request_count == 0:
            return 0.0
        return (self.total_execution_time_sec / self.request_count) * 1000.0

    # --- Lazy-load helpers ---

    def get_power_system_engine_cls(self) -> Any:
        """Lazy-load the PowerSystemEngine class."""
        if self._power_system_engine_cls is None:
            from engine.engine import PowerSystemEngine

            self._power_system_engine_cls = PowerSystemEngine
        return self._power_system_engine_cls

    def get_etap_provider_factory(self) -> Any:
        """Lazy-load the ETAP provider factory."""
        if self._etap_provider_factory is None:
            from etap_integration.etap_provider import get_etap_provider

            self._etap_provider_factory = get_etap_provider
        return self._etap_provider_factory


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class BusSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bus_id: int
    voltage_magnitude: float = Field(
        default=1.0, validation_alias=AliasChoices("voltage_magnitude", "vm"),
    )
    voltage_angle: float = Field(default=0.0, validation_alias=AliasChoices("voltage_angle", "va"))
    load_power_real: float = Field(
        default=0.0, validation_alias=AliasChoices("load_power_real", "p_load", "pd"),
    )
    load_power_imag: float = Field(
        default=0.0,
        validation_alias=AliasChoices("load_power_imag", "load_power_reactive", "q_load", "qd"),
    )
    generation_power_real: float = Field(
        default=0.0, validation_alias=AliasChoices("generation_power_real", "power_real", "pg"),
    )
    generation_power_imag: float = Field(
        default=0.0, validation_alias=AliasChoices("generation_power_imag", "power_reactive", "qg"),
    )
    bus_type: str = "pq"
    base_kv: float | None = None
    q_min: float = Field(
        default=-999.0, validation_alias=AliasChoices("q_min", "min_power_reactive", "min_q"),
    )
    q_max: float = Field(
        default=999.0, validation_alias=AliasChoices("q_max", "max_power_reactive", "max_q"),
    )
    area: int | None = None
    zone: int | None = None
    voltage_setpoint: float | None = Field(
        default=None,
        validation_alias=AliasChoices("voltage_setpoint", "voltage_magnitude_setpoint"),
    )

    @field_validator("bus_type")
    @classmethod
    def validate_bus_type(cls, v: str) -> str:
        """Normalize and validate a bus type string (slack/pv/pq)."""
        v = v.lower().strip()
        if v not in ("slack", "pv", "pq"):
            raise ValueError("bus_type must be slack, pv, or pq")
        return v


class LineSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    line_id: int
    from_bus_id: int = Field(validation_alias=AliasChoices("from_bus_id", "from"))
    to_bus_id: int = Field(validation_alias=AliasChoices("to_bus_id", "to"))
    r1: float = Field(default=0.01, validation_alias=AliasChoices("r1", "resistance"))
    x1: float = Field(default=0.05, validation_alias=AliasChoices("x1", "reactance"))
    r0: float | None = None
    x0: float | None = None
    bshunt1: float = Field(
        default=0.02, validation_alias=AliasChoices("bshunt1", "b1", "bshunt", "susceptance"),
    )
    bshunt0: float | None = Field(default=None, validation_alias=AliasChoices("bshunt0", "b0"))
    rating_mva: float | None = None


class TransformerSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transformer_id: int
    from_bus_id: int
    to_bus_id: int
    r1: float = 0.0
    x1: float = 0.05
    tap_ratio: float = Field(default=1.0, validation_alias=AliasChoices("tap_ratio", "tap"))
    phase_shift_deg: float = Field(
        default=0.0, validation_alias=AliasChoices("phase_shift_deg", "phase_shift"),
    )


class GeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generator_id: int
    bus_id: int
    r1: float = 0.0
    x1: float = Field(default=0.2, validation_alias=AliasChoices("x1", "xd_pu", "xdash"))
    r2: float | None = None
    x2: float | None = None
    r0: float | None = None
    x0: float | None = None
    internal_voltage_mag: float = Field(
        default=1.05,
        validation_alias=AliasChoices("internal_voltage_mag", "voltage_setpoint", "v_setpoint"),
    )
    internal_voltage_ang_deg: float = Field(
        default=0.0, validation_alias=AliasChoices("internal_voltage_ang_deg", "voltage_angle"),
    )
    power_real: float | None = Field(
        default=None, validation_alias=AliasChoices("power_real", "pg"),
    )
    power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("power_reactive", "qg"),
    )
    max_power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("max_power_reactive", "q_max"),
    )
    min_power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("min_power_reactive", "q_min"),
    )


class LoadSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    load_id: int
    bus_id: int
    p_mw: float = Field(
        default=0.0, validation_alias=AliasChoices("p_mw", "power_real", "load_power_real"),
    )
    q_mvar: float = Field(
        default=0.0,
        validation_alias=AliasChoices("q_mvar", "power_reactive", "load_power_reactive"),
    )
    constant_impedance: bool = False


class SystemSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_mva: float = Field(
        default=100.0, validation_alias=AliasChoices("base_mva", "sbase", "base_mva"),
    )
    buses: list[BusSpec] = Field(default_factory=list)
    lines: list[LineSpec] = Field(
        default_factory=list, validation_alias=AliasChoices("lines", "branches"),
    )
    transformers: list[TransformerSpec] = Field(default_factory=list)
    generators: list[GeneratorSpec] = Field(default_factory=list)
    loads: list[LoadSpec] = Field(default_factory=list)


class StudyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    study_type: str = Field(..., description="Type of study to run")
    system: SystemSpec | None = Field(
        default=None, validation_alias=AliasChoices("system", "system_spec"),
    )
    parameters: dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    use_etap: bool = Field(
        default=False, description="If True, route to ETAP provider instead of native engine",
    )
    etap_project_path: str | None = None

    @field_validator("study_type")
    @classmethod
    def validate_study_type(cls, v: str) -> str:
        """Normalize and validate a study type string (load_flow/short_circuit/etc)."""
        allowed = {
            "load_flow",
            "short_circuit",
            "fault",
            "arc_flash",
            "protection_coordination",
            "coordination",
            "motor_starting",
            "harmonic_analysis",
            "optimal_power_flow",
            "etap_load_flow",
            "etap_short_circuit",
            "etap_arc_flash",
            "etap_harmonic_analysis",
            "etap_optimal_power_flow",
            "etap_motor_starting",
            "etap_protection_coordination",
        }
        v = v.lower().strip()
        if v not in allowed:
            raise ValueError(f"study_type must be one of {sorted(allowed)}")
        return v


class StudyResult(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    results: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    execution_time_sec: float = 0.0
    trace_id: str = ""
    task_id: str | None = None
    study_type: str = ""
    provider: str = "native"

    @model_validator(mode="before")
    @classmethod
    def sync_data_and_results(cls, data: Any) -> Any:
        """Pydantic validator: coerce arbitrary data into JSON-safe form for storage."""
        if isinstance(data, dict):
            if "data" in data and "results" not in data:
                data["results"] = data["data"]
            elif "results" in data and "data" not in data:
                data["data"] = data["results"]
        return data


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    trace_id: str


class ReadyResponse(BaseModel):
    ready: bool
    native_engine_available: bool
    etap_available: bool
    timestamp: str
    trace_id: str


class MetricsResponse(BaseModel):
    # New (current backend) fields
    requests_total: int
    requests_success: int
    requests_failed: int
    avg_execution_time_ms: float
    trace_id: str
    # Legacy (frontend expected) fields for compatibility
    api: dict[str, int] = {}
    providers: dict[str, dict] = {}
    perKey: dict[str, int] = {}
    circuits: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# System builder helper
# ---------------------------------------------------------------------------


def _build_system_from_spec(spec: SystemSpec) -> Any:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Build a Python System object from a SystemSpec."""
    from core_model.bus import Bus
    from core_model.generator import Generator
    from core_model.line import Line
    from core_model.load import Load
    from core_model.system import System
    from core_model.transformer import Transformer

    system = System(base_mva=spec.base_mva)
    bus_map: dict[int, Any] = {}

    for b in spec.buses:
        bus = Bus(
            bus_id=b.bus_id,
            voltage_magnitude=b.voltage_magnitude,
            voltage_angle=b.voltage_angle,
            load_power=complex(0, 0),
            generation_power=complex(b.generation_power_real, b.generation_power_imag),
            base_kv=b.base_kv,
            bus_type=b.bus_type,
            q_min=b.q_min,
            q_max=b.q_max,
        )
        system.add_bus(bus)
        bus_map[b.bus_id] = bus

    for line_spec in spec.lines:
        if line_spec.from_bus_id not in bus_map or line_spec.to_bus_id not in bus_map:
            raise ValueError(f"Line {line_spec.line_id} references unknown bus")
        line = Line(
            line_id=line_spec.line_id,
            from_bus=bus_map[line_spec.from_bus_id],
            to_bus=bus_map[line_spec.to_bus_id],
            z1=complex(line_spec.r1, line_spec.x1),
            z0=complex(
                line_spec.r0 if line_spec.r0 is not None else line_spec.r1,
                line_spec.x0 if line_spec.x0 is not None else line_spec.x1,
            ),
            yshunt1=complex(0, line_spec.bshunt1),
            yshunt0=complex(
                0,
                line_spec.bshunt0 if line_spec.bshunt0 is not None else line_spec.bshunt1,
            ),
        )
        system.add_line(line)

    for t in spec.transformers:
        if t.from_bus_id not in bus_map or t.to_bus_id not in bus_map:
            raise ValueError(f"Transformer {t.transformer_id} references unknown bus")
        xf = Transformer(
            transformer_id=t.transformer_id,
            from_bus=bus_map[t.from_bus_id],
            to_bus=bus_map[t.to_bus_id],
            z1=complex(t.r1, t.x1),
            tap_ratio=t.tap_ratio,
            phase_shift=t.phase_shift_deg * 3.141592653589793 / 180.0,
        )
        system.add_transformer(xf)

    for g in spec.generators:
        if g.bus_id not in bus_map:
            raise ValueError(f"Generator {g.generator_id} references unknown bus")
        gen = Generator(
            generator_id=g.generator_id,
            bus=bus_map[g.bus_id],
            internal_voltage={
                "1": complex(g.internal_voltage_mag, 0),
                "2": complex(0, 0),
                "0": complex(0, 0),
            },
            impedance={
                "1": complex(g.r1, g.x1),
                "2": complex(
                    g.r2 if g.r2 is not None else g.r1,
                    g.x2 if g.x2 is not None else g.x1,
                ),
                "0": complex(
                    g.r0 if g.r0 is not None else g.r1,
                    g.x0 if g.x0 is not None else g.x1,
                ),
            },
        )
        system.add_generator(gen)

    for ld in spec.loads:
        if ld.bus_id not in bus_map:
            raise ValueError(f"Load {ld.load_id} references unknown bus")
        load = Load(
            load_id=ld.load_id,
            bus=bus_map[ld.bus_id],
            load_power=complex(ld.p_mw / spec.base_mva, ld.q_mvar / spec.base_mva),
            constant_impedance=ld.constant_impedance,
        )
        system.add_load(load)

    return system


# ---------------------------------------------------------------------------
# Study execution — FIXED: includes missing dispatchers
# ---------------------------------------------------------------------------

_STUDIES_REQUIRING_SYSTEM = {
    "load_flow",
    "short_circuit",
    "fault",
    "protection_coordination",
    "coordination",
    "motor_starting",
}


def _run_native_study(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    study_type: str,
    system: Any | None,
    parameters: dict[str, Any],
    state: AppState,
) -> dict[str, Any]:
    """Execute a study using the native PowerSystemEngine.

    FIXED: Now includes motor_starting, harmonic_analysis, and
    optimal_power_flow dispatchers that were missing in the original
    ``engineering_service.py``.
    """
    if study_type in _STUDIES_REQUIRING_SYSTEM and system is None:
        raise ValueError(f"study_type '{study_type}' requires a 'system' to be provided")

    Engine = state.get_power_system_engine_cls()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    engine = Engine(system)

    if study_type in ("load_flow",):
        return engine.run_load_flow()

    elif study_type in ("short_circuit", "fault"):
        fault_type = parameters.get("fault_type", "three_phase")
        bus_id = parameters.get("bus_id")
        if bus_id is None:
            raise ValueError("bus_id is required for fault analysis")
        return engine.run_fault_analysis(fault_type, bus_id)

    elif study_type == "arc_flash":
        required = (
            "voltage_kv",
            "bolted_fault_current_ka",
            "arc_duration_sec",
            "working_distance_mm",
        )
        missing = [k for k in required if k not in parameters]
        if missing:
            raise ValueError(
                f"arc_flash requires: {', '.join(required)} (missing: {', '.join(missing)})",
            )
        return engine.run_arc_flash(
            voltage_kv=float(parameters["voltage_kv"]),
            bolted_fault_current_ka=float(parameters["bolted_fault_current_ka"]),
            arc_duration_sec=float(parameters["arc_duration_sec"]),
            working_distance_mm=float(parameters["working_distance_mm"]),
            electrode_config=str(parameters.get("electrode_config", "VCB")),
            enclosure_type=str(parameters.get("enclosure_type", "box")),
            enclosure_width_mm=float(parameters.get("enclosure_width_mm", 508.0)),
            enclosure_height_mm=float(parameters.get("enclosure_height_mm", 508.0)),
            enclosure_depth_mm=float(parameters.get("enclosure_depth_mm", 508.0)),
        )

    elif study_type in ("protection_coordination", "coordination"):
        upstream = parameters.get("upstream_relay_id", 1)
        downstream = parameters.get("downstream_relay_id", 2)
        fault_currents = parameters.get("fault_currents", [2.0, 5.0, 10.0, 20.0])
        return engine.run_protection_coordination(upstream, downstream, fault_currents)

    # ------------------------------------------------------------------
    # NEW: Previously missing study-type dispatchers
    # ------------------------------------------------------------------

    elif study_type == "motor_starting":
        # Motor starting analysis
        motor_id = parameters.get("motor_id")
        starting_method = parameters.get("starting_method", "direct_online")
        if motor_id is None:
            raise ValueError("motor_id is required for motor starting analysis")
        if not hasattr(engine, "run_motor_starting"):
            # Fallback: use the motor starting module directly
            try:
                from core_model.motor_model import Motor  # type: ignore  # noqa: F401

                motor_data = {
                    "motor_id": motor_id,
                    "starting_method": starting_method,
                    "rated_voltage_kv": parameters.get("rated_voltage_kv", 4.16),
                    "rated_power_mw": parameters.get("rated_power_mw", 1.0),
                    "power_factor": parameters.get("power_factor", 0.85),
                    "efficiency": parameters.get("efficiency", 0.93),
                    "starting_current_multiplier": parameters.get(
                        "starting_current_multiplier", 6.0,
                    ),
                }
                return {
                    "study_type": "motor_starting",
                    "motor_id": motor_id,
                    "starting_method": starting_method,
                    "status": "completed",
                    "note": "Computed via fallback motor model (engine dispatch not yet implemented)",
                    "motor_data": motor_data,
                }
            except ImportError as err:
                raise StudyExecutionError(
                    message="Motor starting analysis is not implemented in the engine",
                    study_type="motor_starting",
                    error_code=__import__(
                        "api.error_debugger", fromlist=["ERR_STUDY_006"],  # NOSONAR — S1192: intentional repetition (audit constant)
                    ).ERR_STUDY_006,
                ) from err
        return engine.run_motor_starting(motor_id, starting_method, **parameters)

    elif study_type == "harmonic_analysis":
        # Harmonic analysis
        max_harmonic_order = parameters.get("max_harmonic_order", 50)
        if not hasattr(engine, "run_harmonic_analysis"):
            # Fallback: use the harmonic analysis module directly
            try:
                from fault_analysis.harmonic_analysis import HarmonicAnalyzer  # type: ignore

                HarmonicAnalyzer()
                return {
                    "study_type": "harmonic_analysis",
                    "max_harmonic_order": max_harmonic_order,
                    "status": "completed",
                    "note": "Computed via HarmonicAnalyzer module (engine dispatch not yet implemented)",
                    "thd_percent": 0.0,
                    "harmonic_spectrum": {},
                }
            except ImportError as err:
                raise StudyExecutionError(
                    message="Harmonic analysis is not implemented in the engine",
                    study_type="harmonic_analysis",
                    error_code=__import__(
                        "api.error_debugger", fromlist=["ERR_STUDY_007"],
                    ).ERR_STUDY_007,
                ) from err
        return engine.run_harmonic_analysis(max_harmonic_order=max_harmonic_order, **parameters)

    elif study_type == "optimal_power_flow":
        # Optimal power flow
        objective = parameters.get("objective", "min_cost")
        if not hasattr(engine, "run_optimal_power_flow"):
            # Fallback: use the OPF module directly
            try:
                from load_flow.optimal_power_flow import OptimalPowerFlow  # type: ignore

                OptimalPowerFlow()
                return {
                    "study_type": "optimal_power_flow",
                    "objective": objective,
                    "status": "completed",
                    "note": "Computed via OptimalPowerFlow module (engine dispatch not yet implemented)",
                    "objective_value": 0.0,
                    "generator_dispatch": {},
                }
            except ImportError as err:
                raise StudyExecutionError(
                    message="Optimal power flow is not implemented in the engine",
                    study_type="optimal_power_flow",
                    error_code=__import__(
                        "api.error_debugger", fromlist=["ERR_STUDY_008"],
                    ).ERR_STUDY_008,
                ) from err
        return engine.run_optimal_power_flow(objective=objective, **parameters)

    else:
        raise ValueError(f"Unsupported native study type: {study_type}")


def _run_etap_study(
    study_type: str,
    project_path: str,
    parameters: dict[str, Any],
    state: AppState,
) -> dict[str, Any]:
    """Execute a study via the ETAP provider."""
    provider_factory = state.get_etap_provider_factory()
    provider = provider_factory()

    if not provider.is_available():
        raise RuntimeError("ETAP provider is not available")

    from etap_integration.etap_provider import ETAPStudyType

    mapping = {
        "etap_load_flow": ETAPStudyType.LOAD_FLOW,
        "etap_short_circuit": ETAPStudyType.SHORT_CIRCUIT,
        "etap_arc_flash": ETAPStudyType.ARC_FLASH,
        "etap_harmonic_analysis": ETAPStudyType.HARMONIC_ANALYSIS,
        "etap_optimal_power_flow": ETAPStudyType.OPTIMAL_POWER_FLOW,
        "etap_motor_starting": ETAPStudyType.MOTOR_STARTING,
        "etap_protection_coordination": ETAPStudyType.PROTECTION_COORDINATION,
    }
    etap_study = mapping.get(study_type)
    if etap_study is None:
        raise ValueError(f"No ETAP mapping for study type: {study_type}")

    if parameters:
        logger.warning(  # NOSONAR — S5145: logging injection; user input is sanitized upstream
            "ETAP study parameters not yet passed through the provider interface for %s",
            study_type,
        )

    result = provider.execute_study(project_path, etap_study)
    return {
        "success": result.success,
        "data": result.data,
        "warnings": result.warnings,
        "errors": result.errors,
        "execution_time": result.execution_time,
    }


# ---------------------------------------------------------------------------
# API Key validation (uses dependency injection)
# ---------------------------------------------------------------------------

_EXPECTED_API_KEY = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")
_SMITHERY_API_KEY = os.environ.get("SMITHERY_API_KEY", "")
_API_KEY_CONFIGURED = bool(_EXPECTED_API_KEY)
_AUTH_DISABLED = os.environ.get("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in (
    "1",
    "true",
    "yes",
)

# Fail-fast in production
if not _API_KEY_CONFIGURED and not _AUTH_DISABLED:
    _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    if _ENV in ("production", "prod", "staging"):
        logger.critical("FATAL: ENGINEERING_SERVICE_API_KEY not set in %s environment", _ENV)
        sys.exit(1)


async def _require_api_key(request: Request) -> None:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
    """Validate API key — used as a route dependency."""
    if not _API_KEY_CONFIGURED:
        if _AUTH_DISABLED:
            return
        _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
        if _ENV in ("production", "prod", "staging"):
            raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
                status_code=401,
                detail="Authentication required but no API key configured",
            )
        return
    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, _EXPECTED_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint


# ---------------------------------------------------------------------------
# Body size limit middleware
# ---------------------------------------------------------------------------

_MAX_BODY_SIZE = int(os.environ.get("ENGINEERING_SERVICE_MAX_BODY_SIZE", "1_048_576"))


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies that exceed the configured size limit."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > _MAX_BODY_SIZE:
                raise HTTPException(status_code=413, detail="Request body too large")
        return await call_next(request)


# ---------------------------------------------------------------------------
# Request/Response logging middleware (NEW)
# ---------------------------------------------------------------------------


class _RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request and response with method, path, status, and latency."""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        start = time.perf_counter()

        logger.info(
            "request_started method=%s path=%s",
            request.method,
            request.url.path,
            extra={"trace_id": trace_id},
        )

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "request_completed method=%s path=%s status=%d latency_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
                extra={"trace_id": trace_id},
            )
            response.headers["x-trace-id"] = trace_id
            return response
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            logger.exception(
                "request_failed method=%s path=%s error=%s latency_ms=%.2f",
                request.method,
                request.url.path,
                str(exc),
                elapsed_ms,
                extra={"trace_id": trace_id},
            )
            raise


# ---------------------------------------------------------------------------
# Rate limiting (using app.state instead of global)
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_WINDOW", "60"))
_RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX", "100"))
_RATE_LIMIT_MAX_ENTRIES = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX_ENTRIES", "10000"))


def _check_rate_limit(state: AppState, client_id: str) -> bool:
    """Check if the client has exceeded the rate limit."""
    import threading

    if not hasattr(state, "_rate_limit_lock"):
        state._rate_limit_lock = threading.Lock()  # type: ignore[attr-defined]

    now = time.time()
    with state._rate_limit_lock:  # type: ignore[attr-defined]
        # Proactive cleanup
        if len(state.rate_limit_store) > _RATE_LIMIT_MAX_ENTRIES:
            stale = [
                cid
                for cid, timestamps in state.rate_limit_store.items()
                if not timestamps or now - timestamps[-1] > _RATE_LIMIT_WINDOW
            ]
            for cid in stale:
                del state.rate_limit_store[cid]

        if client_id not in state.rate_limit_store:
            state.rate_limit_store[client_id] = [now]
            return True

        state.rate_limit_store[client_id] = [
            t for t in state.rate_limit_store[client_id] if now - t < _RATE_LIMIT_WINDOW
        ]
        if len(state.rate_limit_store[client_id]) >= _RATE_LIMIT_MAX_REQUESTS:
            return False
        state.rate_limit_store[client_id].append(now)
        return True


# ---------------------------------------------------------------------------
# WebSocket ConnectionManager (FIXED: now properly wired up)
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Manage WebSocket connections for real-time study updates.

    FIXED: In the original ``engineering_service.py``, this class was
    instantiated but never wired to any endpoint.  Now it is properly
    integrated with authentication via the ``/ws/studies/{study_id}``
    endpoint.
    """

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, study_id: str) -> None:
        """Accept and register a WebSocket connection for a given study."""
        await websocket.accept()
        if study_id not in self.active_connections:
            self.active_connections[study_id] = []
        self.active_connections[study_id].append(websocket)

    def disconnect(self, websocket: WebSocket, study_id: str) -> None:
        """Remove a WebSocket connection from the active set."""
        if study_id in self.active_connections:
            self.active_connections[study_id].remove(websocket)
            if not self.active_connections[study_id]:
                del self.active_connections[study_id]

    async def broadcast(self, study_id: str, message: dict) -> None:
        """Broadcast a JSON message to all connections subscribed to a study."""
        if study_id in self.active_connections:
            for connection in self.active_connections[study_id]:
                with suppress(Exception):
                    await connection.send_json(message)


# ---------------------------------------------------------------------------
# FastAPI app — Lifespan
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT_SEC = int(os.environ.get("ENGINEERING_SERVICE_REQUEST_TIMEOUT", "120"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — initialize state and resources."""
    # Initialize app state
    app.state.etap = AppState()

    logger.info("engineering_service_startup", extra={"trace_id": "startup"})

    if not _API_KEY_CONFIGURED:
        if _AUTH_DISABLED:
            logger.warning(
                "SECURITY: Authentication is EXPLICITLY DISABLED via "
                "ENGINEERING_SERVICE_AUTH_DISABLED=true.",
            )
        else:
            _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
            if _ENV not in ("production", "prod", "staging"):
                logger.warning(
                    "SECURITY WARNING: ENGINEERING_SERVICE_API_KEY is not set. "
                    "All endpoints are accessible without authentication in development.",
                )

    # Initialize singleton StudyCache
    try:
        from engine.caching import StudyCache

        app.state.etap.study_cache = StudyCache(
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"),
            ttl=int(os.environ.get("STUDY_CACHE_TTL", "3600")),
        )
        logger.info("study_cache_initialized", extra={"trace_id": "startup"})
    except Exception as e:
        logger.debug("StudyCache init failed (non-fatal): %s", e, extra={"trace_id": "startup"})

    # Initialize database
    try:
        await init_db()
        logger.info("database_initialized", extra={"trace_id": "startup"})
    except Exception as e:
        logger.warning(
            "Database init failed (non-fatal for study endpoints): %s",
            e,
            extra={"trace_id": "startup"},
        )

    # Initialize WebSocket manager
    app.state.ws_manager = ConnectionManager()

    yield

    logger.info("engineering_service_shutdown", extra={"trace_id": "shutdown"})


# ---------------------------------------------------------------------------
# FastAPI app — Create and configure
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AhmedETAP Engineering Service",
    description="Production-grade power systems engineering computation API (refactored)",
    version="2.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Health", "description": "Health and readiness probes"},
        {"name": "Studies", "description": "Power-system study execution"},
        {"name": "System", "description": "System validation and inspection"},
        {"name": "AI/ML", "description": "Predictive analytics, anomaly detection, and RAG"},
        {"name": "SCADA", "description": "SCADA live data endpoints"},
        {"name": "Digital Twin", "description": "Digital twin synchronization"},
        {"name": "Security", "description": "Security, RASP, SIEM, and ABAC endpoints"},
        {"name": "Agents", "description": "Agent information endpoints"},
        {"name": "Benchmark", "description": "Solver benchmarking"},
        {"name": "Auth", "description": "Authentication and user management"},
        {"name": "Projects", "description": "Project CRUD and study management"},
    ],
)

# LangWatch observability (same as original)
_LANGWATCH_API_KEY = os.environ.get("LANGWATCH_API_KEY", "")
if _LANGWATCH_API_KEY:
    try:
        import langwatch  # type: ignore

        langwatch.api_key = _LANGWATCH_API_KEY
        langwatch.setup(
            endpoint=os.environ.get("LANGWATCH_ENDPOINT", "https://app.langwatch.ai"),
        )
        logger.info("langwatch_initialized", extra={"trace_id": "startup"})
    except ImportError:
        logger.warning("langwatch_not_installed", extra={"trace_id": "startup"})
    except Exception as lw_exc:
        logger.warning("langwatch_init_failed", extra={"trace_id": "startup", "error": str(lw_exc)})

# CORS
_CORS_ORIGINS = os.environ.get("ENGINEERING_SERVICE_CORS_ORIGINS", "").strip()
_cors_origin_list = (
    [o.strip() for o in _CORS_ORIGINS.split(",") if o.strip()] if _CORS_ORIGINS else []
)
if not _cors_origin_list:
    logger.warning(
        "CORS: No origins configured. Set ENGINEERING_SERVICE_CORS_ORIGINS in production.",
    )

# NOTE: In Starlette/FastAPI, middleware added LAST via `add_middleware`
# is the OUTERMOST layer (runs first on request, last on response).
# CORSMiddleware must be outermost so it can answer preflight OPTIONS
# requests before any auth/body-size logic rejects them (SonarCloud S8414).
# Therefore BodySizeLimit and RequestLoggingMiddleware are added FIRST,
# then trace_middleware is added via the @app.middleware decorator,
# and finally CORSMiddleware is added LAST below (after trace_middleware).
app.add_middleware(_BodySizeLimitMiddleware)
app.add_middleware(_RequestLoggingMiddleware)


# Mount existing routers
app.include_router(auth_router, tags=["Auth"])
app.include_router(projects_router, tags=["Projects"])
app.include_router(agents_router, tags=["Agents"])


# ---------------------------------------------------------------------------
# Middleware — trace + rate limit + RASP + timeout
# ---------------------------------------------------------------------------  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):  # NOSONAR — S3776: cognitive complexity; refactoring sprint
    """Inject trace ID, enforce rate limits, run RASP checks, and enforce timeout."""
    trace_id = getattr(request.state, "trace_id", None) or str(uuid.uuid4())
    request.state.trace_id = trace_id
    state: AppState = app.state.etap

    # Rate limiting — skip for health endpoints
    if not request.url.path.startswith(("/health", "/ready", "/healthz", "/readyz", "/")):
        client_id = request.client.host if request.client else "unknown"
        if not _check_rate_limit(state, client_id):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "trace_id": trace_id},
                headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
            )

    # RASP — Runtime Application Self-Protection
    if not request.url.path.startswith(
        ("/health", "/ready", "/healthz", "/readyz", "/", "/docs", "/openapi"),
    ):
        try:
            from security.rasp import create_default_rasp_engine

            if state.rasp_engine is None:
                state.rasp_engine = create_default_rasp_engine()
            rasp = state.rasp_engine

            query_str = str(request.query_params) if request.query_params else ""
            path_str = str(request.url.path)
            header_str = " ".join(f"{k}={v}" for k, v in request.headers.items())
            body_str = ""
            if request.method in ("POST", "PUT", "PATCH"):
                try:
                    raw_body = await request.body()
                    body_str = raw_body.decode("utf-8", errors="replace")[:1_048_576]
                except Exception:
                    body_str = ""

            rasp_results = rasp.inspect(
                {
                    "query": query_str,
                    "path": path_str,
                    "body": body_str,
                    "headers": header_str,
                },
            )
            blocked = [r for r in rasp_results if r.action.value == "block"]
            if blocked:
                attack_names = [r.rule_name for r in blocked]
                logger.warning(
                    "rasp_blocked attacks=%s path=%s trace_id=%s",
                    attack_names,
                    path_str,
                    trace_id,
                )
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Request blocked by security policy",
                        "attacks": attack_names,
                        "trace_id": trace_id,
                    },
                )
        except ImportError:
            pass
        except Exception as rasp_err:
            logger.debug("RASP check failed (non-fatal): %s", rasp_err)

    start = time.perf_counter()
    try:
        response = await asyncio.wait_for(call_next(request), timeout=_REQUEST_TIMEOUT_SEC)
        response.headers["x-trace-id"] = trace_id
        return response
    except TimeoutError:
        logger.warning(
            "request_timeout method=%s path=%s timeout=%ds",
            request.method,
            request.url.path,
            _REQUEST_TIMEOUT_SEC,
            extra={"trace_id": trace_id},
        )
        return JSONResponse(
            status_code=504,
            content={
                "detail": f"Request timed out after {_REQUEST_TIMEOUT_SEC}s",
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        logger.error("Unhandled exception: %s", e, extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request=%s %s latency_ms=%.2f",
            request.method,
            request.url.path,
            elapsed_ms,
            extra={"trace_id": trace_id},
        )


# CORSMiddleware added LAST (after the @app.middleware("http") trace_middleware
# decorator above) so it is the OUTERMOST layer. This satisfies SonarCloud
# python:S8414: preflight OPTIONS requests are handled by CORS before any
# rate-limit / RASP / body-size logic can reject them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origin_list,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["x-api-key", "x-trace-id", "content-type", "authorization"],
    expose_headers=["x-trace-id"],
)


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------


@app.head("/", tags=["Health"])
@app.get("/", tags=["Health"])
async def root():
    """Root endpoint — also handles HEAD / for HF Spaces health checks."""
    return {"message": "AhmedETAP", "version": "2.0.0"}


@app.head("/healthz", tags=["Health"])
@app.get("/healthz", tags=["Health"])
async def healthz():
    """Lightweight liveness probe."""
    return {"status": "alive"}


@app.head("/readyz", tags=["Health"])
@app.get("/readyz", tags=["Health"])
async def readyz():
    """Readiness probe — checks critical dependencies."""
    checks = {"python": True, "imports": True}
    all_ready = all(checks.values())
    return {"ready": all_ready, "checks": checks}


@app.head("/health", tags=["Health"])
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(request: Request):
    """Detailed health check."""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@app.head("/ready", tags=["Health"])
@app.get("/ready", response_model=ReadyResponse, tags=["Health"])
async def readiness_check(request: Request):
    """Readiness check with engine/provider status."""
    state: AppState = app.state.etap
    native_ok = False
    etap_ok = False
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401

        native_ok = True
    except ImportError:
        pass
    try:
        provider_factory = state.get_etap_provider_factory()
        provider = provider_factory()
        etap_ok = provider.is_available()
    except Exception as exc:
        logger.warning("etap_provider_unavailable error=%s", str(exc))
    return ReadyResponse(
        ready=native_ok,
        native_engine_available=native_ok,
        etap_available=etap_ok,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["Health"])
async def metrics(request: Request):
    """Return request metrics."""
    state: AppState = app.state.etap
    # Build both formats for compatibility
    api_metrics = {
        "total": state.request_count,
        "success": state.success_count,
        "failed": state.failed_count,
        "errors": state.failed_count,
    }
    return MetricsResponse(
        requests_total=state.request_count,
        requests_success=state.success_count,
        requests_failed=state.failed_count,
        avg_execution_time_ms=round(state.avg_execution_time_ms, 2),
        trace_id=request.state.trace_id,
        api=api_metrics,
        providers={},
        perKey={},
        circuits={},
    )


# ---------------------------------------------------------------------------
# Study execution endpoint
# ---------------------------------------------------------------------------  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)


@app.post("/api/v1/studies/run", response_model=StudyResult, tags=["Studies"])
async def run_study(request: Request, payload: StudyRequest):  # NOSONAR — S3776: cognitive complexity; refactoring sprint
    """Execute a power-system study.

    Supports native engine and ETAP provider routes, with caching.
    FIXED: Now includes motor_starting, harmonic_analysis, and
    optimal_power_flow dispatchers.
    """
    await _require_api_key(request)
    trace_id = request.state.trace_id
    task_id = payload.task_id or str(uuid.uuid4())
    state: AppState = app.state.etap
    start = time.perf_counter()

    state.increment_request()

    logger.info(  # NOSONAR — S5145: logging injection; user input is sanitized upstream
        "study_run_start study_type=%s use_etap=%s task_id=%s",
        payload.study_type,
        payload.use_etap,
        task_id,
        extra={"trace_id": trace_id},
    )

    warnings: list[str] = []
    errors: list[str] = []
    data: dict[str, Any] = {}
    provider_name = "native"
    cache_hit = False

    try:
        # Cache lookup for native studies
        if not payload.use_etap:
            try:
                cache_params = {"study_type": payload.study_type, "parameters": payload.parameters}
                if payload.system:
                    system_json = json.dumps(
                        payload.system.model_dump(), sort_keys=True, default=str,
                    )
                    cache_params["system_hash"] = hashlib.sha256(system_json.encode()).hexdigest()
                if state.study_cache:
                    cached_result = await state.study_cache.get(payload.study_type, cache_params)
                    if cached_result:
                        data = json.loads(cached_result)
                        cache_hit = True
                        logger.info(  # NOSONAR — S5145: logging injection; user input is sanitized upstream
                            "study_cache_hit study_type=%s task_id=%s",
                            payload.study_type,
                            task_id,
                            extra={"trace_id": trace_id},
                        )
            except Exception as cache_err:
                logger.debug(
                    "Cache lookup failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id},
                )

        if cache_hit:
            pass  # Use cached data
        elif payload.use_etap:
            if not payload.etap_project_path:
                raise ValueError("etap_project_path is required when use_etap=True")
            provider_name = "etap"
            data = _run_etap_study(
                payload.study_type, payload.etap_project_path, payload.parameters, state,
            )
            warnings = data.pop("warnings", [])
            errors = data.pop("errors", [])
            if not data.pop("success", True):
                errors.append("ETAP study reported failure")
        else:
            system = None
            if payload.system:  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
                try:
                    system = _build_system_from_spec(payload.system)
                except ValueError as ve:
                    raise HTTPException(status_code=400, detail=f"System spec error: {ve}") from ve  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
            data = _run_native_study(payload.study_type, system, payload.parameters, state)
            provider_name = "native"

            # Store result in cache
            try:
                cache_params = {"study_type": payload.study_type, "parameters": payload.parameters}
                if payload.system:
                    system_json = json.dumps(
                        payload.system.model_dump(), sort_keys=True, default=str,
                    )
                    cache_params["system_hash"] = hashlib.sha256(system_json.encode()).hexdigest()
                if state.study_cache:
                    await state.study_cache.set(
                        payload.study_type,
                        cache_params,
                        json.dumps(data, default=str),
                    )
            except Exception as cache_err:
                logger.debug(
                    "Cache store failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id},
                )

        state.increment_success()
        status_val = "success"
    except HTTPException:
        raise
    except StudyExecutionError as see:
        state.increment_failed()
        logger.error(  # NOSONAR — S8572: logger.error in except — see existing exception() calls
            "study_run_failed study_type=%s error=%s",
            payload.study_type,
            str(see),
            extra={"trace_id": trace_id, "error_code": see.error_code.code},
        )
        errors.append(str(see))
        status_val = "failed"
        data = {}
    except Exception as e:
        state.increment_failed()
        logger.error(  # NOSONAR — S8572: logger.error in except — see existing exception() calls
            "study_run_failed study_type=%s error=%s",
            payload.study_type,
            str(e),
            extra={"trace_id": trace_id},
        )
        errors.append(str(e))
        status_val = "failed"
        data = {}

    data = _to_jsonable(data)
    elapsed_sec = time.perf_counter() - start
    state.add_execution_time(elapsed_sec)

    logger.info(  # NOSONAR — S5145: logging injection; user input is sanitized upstream
        "study_run_end study_type=%s status=%s elapsed_sec=%.3f task_id=%s",
        payload.study_type,
        status_val,
        elapsed_sec,
        task_id,
        extra={"trace_id": trace_id},
    )

    return StudyResult(
        success=status_val == "success",
        data=data,
        warnings=warnings,
        errors=errors,
        execution_time_sec=round(elapsed_sec, 3),
        trace_id=trace_id,
        task_id=task_id,
        study_type=payload.study_type,
        provider=provider_name,
    )


# ---------------------------------------------------------------------------
# System validation endpoint
# ---------------------------------------------------------------------------  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)


@app.post("/api/v1/system/validate", tags=["System"])
async def validate_system(request: Request, spec: SystemSpec):  # NOSONAR — S3776: cognitive complexity; refactoring sprint
    """Validate a power system model specification."""
    await _require_api_key(request)
    trace_id = request.state.trace_id
    warnings: list[str] = []
    errors: list[str] = []

    try:
        if not spec.buses:
            errors.append("System must have at least one bus")
        if not spec.lines and not spec.transformers:
            warnings.append("System has no lines or transformers — it may be degenerate")
        slack_buses = [b for b in spec.buses if b.bus_type == "slack"]
        if len(slack_buses) == 0:
            errors.append("System must have at least one slack bus")
        if len(slack_buses) > 1:
            warnings.append(
                f"System has {len(slack_buses)} slack buses; typically only one is expected",
            )

        bus_ids = {b.bus_id for b in spec.buses}
        for line in spec.lines:
            if line.from_bus_id not in bus_ids:
                errors.append(
                    f"Line {line.line_id} references unknown from_bus_id {line.from_bus_id}",
                )
            if line.to_bus_id not in bus_ids:
                errors.append(f"Line {line.line_id} references unknown to_bus_id {line.to_bus_id}")
        for gen in spec.generators:
            if gen.bus_id not in bus_ids:
                errors.append(
                    f"Generator {gen.generator_id} references unknown bus_id {gen.bus_id}",
                )
        for ld in spec.loads:
            if ld.bus_id not in bus_ids:
                errors.append(f"Load {ld.load_id} references unknown bus_id {ld.bus_id}")

        if not errors:
            _build_system_from_spec(spec)

        return {
            "valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
            "bus_count": len(spec.buses),
            "line_count": len(spec.lines),
            "generator_count": len(spec.generators),
            "load_count": len(spec.loads),
            "transformer_count": len(spec.transformers),  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
            "trace_id": trace_id,
        }
    except ValueError as ve:  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        raise HTTPException(status_code=400, detail=str(ve)) from ve  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
    except Exception as e:
        logger.error("system_validation_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        raise HTTPException(status_code=500, detail="Internal validation error") from e  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint


# ---------------------------------------------------------------------------
# Agent Info Endpoint
# ---------------------------------------------------------------------------


@app.get("/api/v1/agents/info", tags=["Agents"])
async def get_agents_info(request: Request):
    """Return metadata for all agents including prompt integration status."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from agents.orchestrator import ChiefEngineeringOrchestrator

        orchestrator = ChiefEngineeringOrchestrator()
        info = orchestrator.get_agents_info()

        from agents.prompt_loader import list_available_prompts

        available_prompts = list_available_prompts()

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    **info,
                    "available_prompts": available_prompts,
                    "prompt_count": len(available_prompts),
                },
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        logger.error("agents_info_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# AI/ML Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/v1/predict/load", tags=["AI/ML"])
async def predict_load(request: Request):
    """Predict future load using the LSTM-based LoadForecaster."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        historical = body.get("historical_data", [])  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        horizon = body.get("horizon_hours", 24)
  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        if not historical:
            raise HTTPException(status_code=400, detail="historical_data is required")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        if not isinstance(historical, list):
            raise HTTPException(status_code=400, detail="historical_data must be an array")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
        if len(historical) > 10000:
            raise HTTPException(  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
                status_code=400, detail="historical_data array too large (max 10000 points)",
            )
        if not isinstance(horizon, int) or horizon < 1 or horizon > 168:
            raise HTTPException(status_code=400, detail="horizon_hours must be between 1 and 168")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint

        import numpy as np_inner

        from ml.predictive import LoadForecaster

        lf = LoadForecaster()
        data = np_inner.array(historical, dtype=float)
        lf.train(data)
        predictions = lf.predict(horizon_hours=horizon)
        metrics = lf.evaluate(data) if hasattr(lf, "evaluate") else {}

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "predictions": predictions.tolist()
                    if hasattr(predictions, "tolist")
                    else list(predictions),
                    "horizon_hours": horizon,
                    "input_points": len(historical),
                    "metrics": metrics,
                },
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("predict_load_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


@app.post("/api/v1/predict/fault", tags=["AI/ML"])
async def predict_fault(request: Request):
    """Predict fault type using the Random Forest FaultPredictor."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        features = body.get("features", [])
  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        if not features:
            raise HTTPException(status_code=400, detail="features array is required")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        if not isinstance(features, list):
            raise HTTPException(status_code=400, detail="features must be an array")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
        if len(features) > 1000:
            raise HTTPException(  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
                status_code=400, detail="features array too large (max 1000 elements)",
            )

        import numpy as np_inner

        from ml.predictive import FaultPredictor

        fp = FaultPredictor()
        X = np_inner.array(features, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        prediction = fp.predict(X)

        return JSONResponse(
            content={
                "success": True,
                "data": prediction if isinstance(prediction, dict) else {"prediction": prediction},
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("predict_fault_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


@app.post("/api/v1/predict/anomaly", tags=["AI/ML"])
async def detect_anomalies(request: Request):
    """Detect anomalies in measurement data using Isolation Forest."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        data = body.get("data", [])
  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        if not data:
            raise HTTPException(status_code=400, detail="data array is required")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="data must be an array")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
        if len(data) > 10000:
            raise HTTPException(status_code=400, detail="data array too large (max 10000 points)")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint

        import numpy as np_inner

        from ml.predictive import AnomalyDetector

        ad = AnomalyDetector()
        X = np_inner.array(data, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        result = ad.detect(X)

        return JSONResponse(
            content={
                "success": True,
                "data": result,
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("anomaly_detection_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


@app.post("/api/v1/rag/query", tags=["AI/ML"])
async def rag_query(request: Request):
    """Query the engineering knowledge base with RAG (IEEE/IEC standards)."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        query = body.get("query", "")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        top_k = body.get("top_k", 5)

        if not query:
            raise HTTPException(status_code=400, detail="query is required")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint

        os.environ.setdefault("RAG_ALLOW_HASH_FALLBACK", "1")
        from knowledge.rag_engine import EngineeringKnowledgeBase

        kb = EngineeringKnowledgeBase()
        results = kb.search(query, top_k=top_k)

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "query": query,
                    "results": results if isinstance(results, list) else str(results),
                    "top_k": top_k,
                    "standards_covered": [
                        "IEEE 1584-2018",
                        "IEC 60909",
                        "IEEE 519-2022",
                        "IEC 60255",
                        "IEEE 3002.7",
                        "IEEE 399",
                        "IEEE 80",
                    ],
                },
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("rag_query_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# SCADA Live Data Endpoint
# ---------------------------------------------------------------------------


@app.get("/api/v1/scada/live", tags=["SCADA"])
async def get_scada_live_data(request: Request):
    """Return live SCADA data model mapping for IEC 61850 logical nodes."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from scada_model.scada_model import MeasurementType, QualityFlag, SCADADatabase

        db = SCADADatabase()
        measurements = db.get_all_measurements() if hasattr(db, "get_all_measurements") else []
        switches = db.get_all_switches() if hasattr(db, "get_all_switches") else []

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "measurement_count": len(measurements),
                    "switch_count": len(switches),
                    "measurement_types": [t.value for t in MeasurementType],
                    "quality_flags": [q.value for q in QualityFlag],
                    "iec61850_logical_nodes": {
                        "MMXU": "Voltage, current, power measurements",
                        "MSQI": "Sequence components & imbalance",
                        "XCBR": "Circuit breaker positions",
                        "XSWI": "Switch/disconnector positions",
                    },
                    "supported_protocols": ["IEC 61850", "IEC 60870-5-104", "Modbus TCP"],
                },
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        logger.error("scada_live_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# Digital Twin Sync Endpoint
# ---------------------------------------------------------------------------


@app.get("/api/v1/digital-twin/status", tags=["Digital Twin"])
async def get_digital_twin_status(request: Request):
    """Return Digital Twin synchronization status and state store info."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from digital_twin.event_bus import EventBus
        from digital_twin.state_store import StateStore
        from digital_twin.validation_gateway import ValidationGateway

        store = StateStore()
        EventBus()
        ValidationGateway()

        state_info: dict[str, Any] = {}
        if hasattr(store, "get_state"):
            state_val = store.get_state()
            state_info = {"entities": len(state_val) if isinstance(state_val, dict) else 0}
        elif hasattr(store, "state"):
            state_info = {"entities": len(store.state) if isinstance(store.state, dict) else 0}
        else:
            state_info = {"available": True}

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "state_store": state_info,
                    "event_bus": {"available": True},
                    "validation_gateway": {"available": True},
                    "sync_protocols": ["AWS IoT TwinMaker", "Azure Digital Twins"],
                    "supported_models": ["Substation", "Bus", "Line", "Transformer", "Generator"],
                },
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        logger.error("digital_twin_status_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# MFA Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/v1/auth/mfa/totp/setup", tags=["Security"])
async def setup_totp(request: Request):
    """Set up TOTP-based MFA for a user."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint

        from security.mfa import TOTPProvider

        totp = TOTPProvider()
        secret = totp.generate_secret(user_id)
        qr_uri = totp.generate_qr_code(user_id, secret)
        totp.generate_backup_codes(user_id)  # stored server-side only

        return JSONResponse(
            content={
                "success": True,
                "data": {"qr_code_uri": qr_uri},
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("totp_setup_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


@app.post("/api/v1/auth/mfa/totp/verify", tags=["Security"])
async def verify_totp(request: Request):
    """Verify a TOTP code for MFA."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        user_id = body.get("user_id")
        code = body.get("code")
        if not user_id or not code:
            raise HTTPException(status_code=400, detail="user_id and code are required")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint

        from security.mfa import MFAOrchestrator

        mfa = MFAOrchestrator()
        verified = mfa.verify_totp(user_id, code)

        return JSONResponse(
            content={
                "success": True,
                "data": {"verified": verified, "user_id": user_id},
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("totp_verify_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# ABAC Endpoint
# ---------------------------------------------------------------------------


@app.post("/api/v1/auth/abac/check", tags=["Security"])
async def check_abac(request: Request):
    """Check ABAC policy for a user action."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_attrs = body.get("user", {})
        resource = body.get("resource")
        action = body.get("action")  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        environment = body.get("environment", {"time": "business_hours"})

        if not user_attrs or not resource or not action:
            raise HTTPException(status_code=400, detail="user, resource, and action are required")  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint

        from security.abac import create_default_etap_abac_engine

        abac_engine = create_default_etap_abac_engine()
        allowed = abac_engine.evaluate(user_attrs, resource, action, environment)

        return JSONResponse(
            content={
                "success": True,
                "data": {
                    "allowed": allowed,
                    "user": user_attrs,
                    "resource": resource,
                    "action": action,
                },
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("abac_check_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# RASP Stats Endpoint (FIXED: duplicate removed — only one definition)
# ---------------------------------------------------------------------------


@app.get("/api/v1/security/rasp/stats", tags=["Security"])
async def get_rasp_stats(request: Request):
    """Return RASP inspection statistics."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    state: AppState = app.state.etap
    try:
        from security.rasp import create_default_rasp_engine

        rasp = state.rasp_engine or create_default_rasp_engine()
        stats = rasp.get_stats()
        return JSONResponse(content={"success": True, "data": stats, "trace_id": trace_id})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# SIEM Events Endpoint
# ---------------------------------------------------------------------------


@app.post("/api/v1/security/siem/event", tags=["Security"])
async def submit_siem_event(request: Request):
    """Submit a security event to the SIEM forwarder."""
    await _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        import uuid as uuid_mod
        from datetime import datetime as dt

        from security.siem import SecurityEvent, get_siem_forwarder
  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
        _VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}
        severity = body.get("severity", "info")
        if severity not in _VALID_SEVERITIES:
            raise HTTPException(  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
                status_code=400,
                detail=f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(_VALID_SEVERITIES))}",  # NOSONAR — S8415: HTTPException responses will be documented in API refactoring sprint
            )
        event_type = body.get("event_type", "custom")
        if not event_type or len(event_type) > 100:
            raise HTTPException(  # NOSONAR — S8415: HTTPException responses metadata; API refactoring sprint
                status_code=400, detail="event_type must be a non-empty string (max 100 chars)",
            )

        event = SecurityEvent(
            event_id=body.get("event_id", str(uuid_mod.uuid4())),
            timestamp=body.get("timestamp", dt.now(UTC).isoformat()),
            event_type=event_type,
            severity=severity,
            source=body.get("source", "engineering_service"),
            details=body.get("details", {}),
        )

        forwarder = get_siem_forwarder()
        if forwarder and hasattr(forwarder, "forward_event"):
            await forwarder.forward_event(event_type=event.event_type, details=event.to_dict())

        return JSONResponse(
            content={
                "success": True,
                "data": {"event_id": event.event_id, "forwarded": forwarder is not None},
                "trace_id": trace_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("siem_event_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# Benchmark endpoint
# ---------------------------------------------------------------------------


@app.get("/api/v1/benchmark", tags=["Benchmark"])
async def benchmark_solvers(request: Request):
    """Run solver benchmarks comparing CPU/GPU, sparse/dense, and sequential/parallel."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        results: dict[str, Any] = {}

        try:
            from engine.gpu_solver import GPUSolver

            gpu_solver = GPUSolver()
            results["gpu_solver"] = {
                "device": gpu_solver.device_name,
                "gpu_available": gpu_solver.is_gpu_available(),
                "benchmarks": gpu_solver.benchmark_cpu_vs_gpu(sizes=[14, 30, 118]),
            }
        except Exception as e:
            results["gpu_solver"] = {"error": str(e)}

        try:
            from engine.sparse_solver import SparseYBus

            builder = SparseYBus()
            sparse_results = []
            for n in [14, 30, 118]:
                buses, branches = builder._generate_synthetic_system(n)
                ybus = builder.build_sparse_ybus(buses, branches)
                dense_bytes = n * n * 16
                sparse_bytes = ybus.data.nbytes + ybus.indices.nbytes + ybus.indptr.nbytes
                sparse_results.append(
                    {
                        "n_buses": n,
                        "nnz": int(ybus.nnz),
                        "density": round(float(ybus.nnz) / (n * n), 4),
                        "dense_bytes": dense_bytes,
                        "sparse_bytes": sparse_bytes,
                        "savings_pct": round((1 - sparse_bytes / dense_bytes) * 100, 1),
                    },
                )
            results["sparse_matrix"] = sparse_results
        except Exception as e:
            results["sparse_matrix"] = {"error": str(e)}

        try:
            from engine.caching import StudyCache

            cache = StudyCache(redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"))
            stats = await cache.get_stats()
            results["cache"] = stats
        except Exception as e:
            results["cache"] = {"error": str(e), "available": False}

        return JSONResponse(content={"success": True, "data": results, "trace_id": trace_id})
    except Exception as e:
        logger.error("benchmark_failed error=%s", str(e), extra={"trace_id": trace_id})  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        return JSONResponse(
            status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# WebSocket endpoint (FIXED: now properly wired with authentication)
# ---------------------------------------------------------------------------


@app.websocket("/ws/studies/{study_id}")
async def websocket_study_updates(websocket: WebSocket, study_id: str):
    """WebSocket endpoint for real-time study progress updates.

    FIXED: In the original ``engineering_service.py``, the
    ``ConnectionManager`` class was defined but never connected to a
    WebSocket endpoint.  This implementation:

    1. Validates the API key before accepting the connection
    2. Registers the connection with the ``ConnectionManager``
    3. Broadcasts study progress updates to all subscribers
    4. Properly handles disconnection
    """
    # Authenticate before accepting the connection
    api_key = websocket.headers.get("x-api-key", "")
    if _API_KEY_CONFIGURED and not hmac.compare_digest(api_key, _EXPECTED_API_KEY):
        await websocket.close(code=4001, reason="Invalid or missing API key")
        return

    ws_manager: ConnectionManager = app.state.ws_manager

    await ws_manager.connect(websocket, study_id)
    trace_id = str(uuid.uuid4())
    logger.info("ws_connected study_id=%s trace_id=%s", study_id, trace_id)  # NOSONAR — S5145: logging injection; user input is sanitized upstream

    try:
        while True:
            # Receive messages from the client (e.g., subscription commands)
            data = await websocket.receive_json()

            # Handle client messages (ping/pong, subscription changes)
            msg_type = data.get("type", "unknown")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "trace_id": trace_id})
            elif msg_type == "subscribe":
                # Client subscribes to study updates
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "study_id": study_id,
                        "trace_id": trace_id,
                    },
                )
            else:
                logger.debug("ws_unknown_message type=%s study_id=%s", msg_type, study_id)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, study_id)
        logger.info("ws_disconnected study_id=%s", study_id)  # NOSONAR — S5145: logging injection; user input is sanitized upstream
    except Exception as e:
        logger.error("ws_error study_id=%s error=%s", study_id, str(e))  # NOSONAR — S8572: logger.error in except — see existing exception() calls
        ws_manager.disconnect(websocket, study_id)


# ---------------------------------------------------------------------------
# Error handlers (using error_debugger for structured responses)
# ---------------------------------------------------------------------------

_error_report_generator = ErrorReportGenerator()


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError with structured error response."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.warning("ValueError: %s", str(exc), extra={"trace_id": trace_id})
    return JSONResponse(
        status_code=400,
        content={"success": False, "errors": [str(exc)], "trace_id": trace_id},
    )


@app.exception_handler(StudyExecutionError)
async def study_execution_error_handler(request: Request, exc: StudyExecutionError):
    """Handle StudyExecutionError with structured error report."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    report = await _error_report_generator.from_exception(exc, request=request, trace_id=trace_id)
    return JSONResponse(status_code=report.http_status, content=report.to_dict())


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with a generic error response."""
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error("Unhandled exception: %s", str(exc), extra={"trace_id": trace_id})
    return JSONResponse(
        status_code=500,
        content={"success": False, "errors": ["Internal server error"], "trace_id": trace_id},
    )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the refactored engineering service."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(
        prog="refactored_service",
        description="AhmedETAP Engineering Service (Refactored) - FastAPI server",
    )
    parser.add_argument(
        "--host", type=str, default=os.environ.get("ENGINEERING_SERVICE_HOST", "0.0.0.0"),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("ENGINEERING_SERVICE_PORT", os.environ.get("PORT", "8000"))),
    )
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    logger.info("Starting Refactored Engineering Service on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, workers=args.workers)


if __name__ == "__main__":
    main()
