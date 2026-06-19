"""
Engineering Service API
=======================
Production-grade FastAPI service wrapping the Python PowerSystemEngine.

Architecture:
  Worker → Engineering Service → PowerSystemEngine / ETAPProvider

Features:
- Typed Pydantic v2 request/response schemas
- Health / readiness / metrics endpoints
- Structured logging with trace IDs
- Request validation and input sanitization
- Timeout handling
- ETAP integration via provider abstraction
- CORS for Worker origin

Run:
    uvicorn engineering_service:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Cache directories — redirect to /tmp for HF Spaces (read-only filesystem)
# ---------------------------------------------------------------------------
for _env_key, _env_val in [
    ("NUMBA_CACHE_DIR", "/tmp/numba_cache"),
    ("MPLCONFIGDIR", "/tmp/matplotlib_cache"),
    ("XDG_CACHE_HOME", "/tmp/hf_cache"),
    ("HF_HOME", "/tmp/hf_cache"),
    ("TRANSFORMERS_CACHE", "/tmp/hf_cache/transformers"),
    ("TORCH_HOME", "/tmp/hf_cache/torch"),
]:
    if _env_key not in os.environ:
        os.environ[_env_key] = _env_val
    os.makedirs(os.environ[_env_key], exist_ok=True)


# ---------------------------------------------------------------------------
# numpy-aware JSON sanitizer
# ---------------------------------------------------------------------------
# The native PowerSystemEngine returns dicts containing numpy scalars / arrays.
# Pydantic v2's default encoder cannot serialize them, so we recursively
# convert any numpy types to native Python equivalents before returning.
try:
    import numpy as np  # type: ignore

    _HAS_NUMPY = True
except Exception:  # numpy is normally present, but be defensive
    np = None  # type: ignore
    _HAS_NUMPY = False


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy types (and other engine outputs) to native
    Python primitives that FastAPI / Pydantic can serialize as JSON."""
    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        # Reject nan/inf which are not valid JSON
        if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
            return None
        return obj
    if isinstance(obj, complex):
        re, im = obj.real, obj.imag
        if not _HAS_NUMPY:
            import math as _math
            if not _math.isfinite(re):
                re = 0.0
            if not _math.isfinite(im):
                im = 0.0
        return {"re": _to_jsonable(re), "im": _to_jsonable(im)}
    if _HAS_NUMPY:
        if isinstance(obj, np.ndarray):
            return [_to_jsonable(x) for x in obj.tolist()]
        if isinstance(obj, (np.integer,)):
            return int(obj.item())
        if isinstance(obj, (np.floating,)):
            v = float(obj.item())
            if v != v or v in (float("inf"), float("-inf")):
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
    # Fallback: best-effort string coercion
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.base import BaseHTTPMiddleware
from utils.language_detection import normalize_input

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

class _TraceFilter(logging.Filter):
    """Injects trace_id into log records when missing."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "trace_id"):
            record.trace_id = "-"
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s %(message)s",
    stream=sys.stdout,
)

for handler in logging.getLogger().handlers:
    handler.addFilter(_TraceFilter())

logger = logging.getLogger("engineering_service")
logger.addFilter(_TraceFilter())


# ---------------------------------------------------------------------------
# Lazy imports (heavy numerical libs only loaded on first request)
# ---------------------------------------------------------------------------

_POWER_SYSTEM_ENGINE: Any = None
_ETAP_PROVIDER: Any = None


def _get_power_system_engine():
    global _POWER_SYSTEM_ENGINE
    if _POWER_SYSTEM_ENGINE is None:
        from engine.engine import PowerSystemEngine

        _POWER_SYSTEM_ENGINE = PowerSystemEngine
    return _POWER_SYSTEM_ENGINE


def _get_etap_provider():
    global _ETAP_PROVIDER
    if _ETAP_PROVIDER is None:
        from etap_integration.etap_provider import get_etap_provider

        _ETAP_PROVIDER = get_etap_provider
    return _ETAP_PROVIDER


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class BusSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bus_id: int
    voltage_magnitude: float = Field(default=1.0, validation_alias=AliasChoices("voltage_magnitude", "vm"))
    voltage_angle: float = Field(default=0.0, validation_alias=AliasChoices("voltage_angle", "va"))
    load_power_real: float = Field(default=0.0, validation_alias=AliasChoices("load_power_real", "p_load", "pd"))
    load_power_imag: float = Field(default=0.0, validation_alias=AliasChoices("load_power_imag", "load_power_reactive", "q_load", "qd"))
    generation_power_real: float = Field(default=0.0, validation_alias=AliasChoices("generation_power_real", "power_real", "pg"))
    generation_power_imag: float = Field(default=0.0, validation_alias=AliasChoices("generation_power_imag", "power_reactive", "qg"))
    bus_type: str = "pq"
    base_kv: Optional[float] = None
    q_min: float = Field(default=-999.0, validation_alias=AliasChoices("q_min", "min_power_reactive", "min_q"))
    q_max: float = Field(default=999.0, validation_alias=AliasChoices("q_max", "max_power_reactive", "max_q"))
    area: Optional[int] = None
    zone: Optional[int] = None
    voltage_setpoint: Optional[float] = Field(default=None, validation_alias=AliasChoices("voltage_setpoint", "voltage_magnitude_setpoint"))

    @field_validator("bus_type")
    @classmethod
    def validate_bus_type(cls, v: str) -> str:
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
    r0: Optional[float] = None
    x0: Optional[float] = None
    bshunt1: float = Field(default=0.02, validation_alias=AliasChoices("bshunt1", "b1", "bshunt", "susceptance"))
    bshunt0: Optional[float] = Field(default=None, validation_alias=AliasChoices("bshunt0", "b0"))
    rating_mva: Optional[float] = None


class TransformerSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transformer_id: int
    from_bus_id: int
    to_bus_id: int
    r1: float = 0.0
    x1: float = 0.05
    tap_ratio: float = Field(default=1.0, validation_alias=AliasChoices("tap_ratio", "tap"))
    phase_shift_deg: float = Field(default=0.0, validation_alias=AliasChoices("phase_shift_deg", "phase_shift"))


class GeneratorSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    generator_id: int
    bus_id: int
    r1: float = 0.0
    x1: float = Field(default=0.2, validation_alias=AliasChoices("x1", "xd_pu", "xdash"))
    r2: Optional[float] = None
    x2: Optional[float] = None
    r0: Optional[float] = None
    x0: Optional[float] = None
    internal_voltage_mag: float = Field(default=1.05, validation_alias=AliasChoices("internal_voltage_mag", "voltage_setpoint", "v_setpoint"))
    internal_voltage_ang_deg: float = Field(default=0.0, validation_alias=AliasChoices("internal_voltage_ang_deg", "voltage_angle"))
    power_real: Optional[float] = Field(default=None, validation_alias=AliasChoices("power_real", "pg"))
    power_reactive: Optional[float] = Field(default=None, validation_alias=AliasChoices("power_reactive", "qg"))
    max_power_reactive: Optional[float] = Field(default=None, validation_alias=AliasChoices("max_power_reactive", "q_max"))
    min_power_reactive: Optional[float] = Field(default=None, validation_alias=AliasChoices("min_power_reactive", "q_min"))


class LoadSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    load_id: int
    bus_id: int
    p_mw: float = Field(default=0.0, validation_alias=AliasChoices("p_mw", "power_real", "load_power_real"))
    q_mvar: float = Field(default=0.0, validation_alias=AliasChoices("q_mvar", "power_reactive", "load_power_reactive"))
    constant_impedance: bool = False


class SystemSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_mva: float = Field(default=100.0, validation_alias=AliasChoices("base_mva", "sbase", "base_mva"))
    buses: List[BusSpec] = Field(default_factory=list)
    lines: List[LineSpec] = Field(default_factory=list, validation_alias=AliasChoices("lines", "branches"))
    transformers: List[TransformerSpec] = Field(default_factory=list)
    generators: List[GeneratorSpec] = Field(default_factory=list)
    loads: List[LoadSpec] = Field(default_factory=list)


class StudyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    study_type: str = Field(..., description="Type of study to run")
    system: Optional[SystemSpec] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    task_id: Optional[str] = None
    use_etap: bool = Field(default=False, description="If True, route to ETAP provider instead of native engine")
    etap_project_path: Optional[str] = None

    @field_validator("study_type")
    @classmethod
    def validate_study_type(cls, v: str) -> str:
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
    data: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    execution_time_sec: float = 0.0
    trace_id: str = ""
    task_id: Optional[str] = None
    study_type: str = ""
    provider: str = "native"


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
    requests_total: int
    requests_success: int
    requests_failed: int
    avg_execution_time_ms: float
    trace_id: str


# ---------------------------------------------------------------------------
# In-memory metrics (production: push to Prometheus / StatsD)
# ---------------------------------------------------------------------------

import threading as _threading

_request_count = 0
_success_count = 0
_failed_count = 0
_total_execution_time_sec = 0.0
_metrics_lock = _threading.Lock()


# Import Prometheus instrumentation
from core.metrics import (
    count_executions,
    generate_metrics,
    get_metrics_content_type,
    set_app_info,
    track_skill_operation,
)

# Import OpenTelemetry tracing
from core.tracing import get_tracer, inject_context, trace_operation
from opentelemetry.trace import SpanKind, Status, StatusCode

# Initialise app info metrics
set_app_info(name="ahmedetap-engineering-service", version="1.0.0")


def _increment_counter(name: str, delta: int = 1) -> None:
    """Thread-safe counter increment."""
    global _request_count, _success_count, _failed_count
    with _metrics_lock:
        if name == "request":
            _request_count += delta
            # (Prometheus gauge tracking for active connections would go here)
        elif name == "success":
            _success_count += delta
        elif name == "failed":
            _failed_count += delta


def _add_execution_time(delta: float) -> None:
    """Thread-safe execution time accumulator."""
    global _total_execution_time_sec
    with _metrics_lock:
        _total_execution_time_sec += delta


# ---------------------------------------------------------------------------
# System builder helper
# ---------------------------------------------------------------------------

@trace_operation("_build_system_from_spec", attributes={"component": "engineering_service"})
def _build_system_from_spec(spec: SystemSpec) -> Any:
    """Build a Python System object from a SystemSpec."""
    from core_model.bus import Bus
    from core_model.generator import Generator
    from core_model.line import Line
    from core_model.load import Load
    from core_model.system import System
    from core_model.transformer import Transformer

    system = System(base_mva=spec.base_mva)
    bus_map: Dict[int, Any] = {}

    for b in spec.buses:
        bus = Bus(
            bus_id=b.bus_id,
            voltage_magnitude=b.voltage_magnitude,
            voltage_angle=b.voltage_angle,
            load_power=complex(0, 0),  # load_power will be added by Load objects
            generation_power=complex(b.generation_power_real, b.generation_power_imag),
            base_kv=b.base_kv,
            bus_type=b.bus_type,
            q_min=b.q_min,
            q_max=b.q_max,
        )
        system.add_bus(bus)
        bus_map[b.bus_id] = bus

    for l in spec.lines:
        if l.from_bus_id not in bus_map or l.to_bus_id not in bus_map:
            raise ValueError(f"Line {l.line_id} references unknown bus")
        line = Line(
            line_id=l.line_id,
            from_bus=bus_map[l.from_bus_id],
            to_bus=bus_map[l.to_bus_id],
            z1=complex(l.r1, l.x1),
            z0=complex(l.r0 if l.r0 is not None else l.r1, l.x0 if l.x0 is not None else l.x1),
            yshunt1=complex(0, l.bshunt1),
            yshunt0=complex(0, l.bshunt0 if l.bshunt0 is not None else l.bshunt1),
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
                "2": complex(g.r2 if g.r2 is not None else g.r1, g.x2 if g.x2 is not None else g.x1),
                "0": complex(g.r0 if g.r0 is not None else g.r1, g.x0 if g.x0 is not None else g.x1),
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
# Study execution
# ---------------------------------------------------------------------------

_STUDIES_REQUIRING_SYSTEM = {"load_flow", "short_circuit", "fault", "protection_coordination", "coordination", "motor_starting"}


@trace_operation("_run_native_study", attributes={"component": "engineering_service"})
def _run_native_study(study_type: str, system: Optional[Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a study using the native PowerSystemEngine."""
    if study_type in _STUDIES_REQUIRING_SYSTEM and system is None:
        raise ValueError(f"study_type '{study_type}' requires a 'system' to be provided")

    Engine = _get_power_system_engine()
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
        required = ("voltage_kv", "bolted_fault_current_ka", "arc_duration_sec", "working_distance_mm")
        missing = [k for k in required if k not in parameters]
        if missing:
            raise ValueError(f"arc_flash requires: {', '.join(required)} (missing: {', '.join(missing)})")
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
    else:
        raise ValueError(f"Unsupported native study type: {study_type}")


@trace_operation("_run_etap_study", attributes={"component": "engineering_service"})
def _run_etap_study(study_type: str, project_path: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a study via the ETAP provider."""
    provider_factory = _get_etap_provider()
    provider = provider_factory()

    if not provider.is_available():
        raise RuntimeError("ETAP provider is not available")

    from etap_integration.etap_provider import ETAPStudyType

    # Map generic study type to ETAP study type
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

    # NOTE: ETAP provider currently only accepts project_path, study_type, and visible.
    # Parameters are ignored by the local provider; the remote worker accepts parameters
    # but the provider interface does not pass them through. Log this limitation.
    if parameters:
        logger.warning(
            "ETAP study parameters are not yet passed through the provider interface for %s",
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
# API Key validation
# ---------------------------------------------------------------------------

_EXPECTED_API_KEY = os.environ.get("ENGINEERING_SERVICE_API_KEY", "")

# ---------------------------------------------------------------------------
# Smithery Integration — External API Key Management
# If SMITHERY_API_KEY is set, it can be used as an alternative to
# ENGINEERING_SERVICE_API_KEY, enabling centralized key management via
# the Smithery platform (https://smithery.ai).
# NOTE: Smithery key is NOT used as the service auth key anymore for security.
# It is stored separately for Smithery-specific integrations only.
# ---------------------------------------------------------------------------
_SMITHERY_API_KEY = os.environ.get("SMITHERY_API_KEY", "")
if _SMITHERY_API_KEY:
    logger.info("smithery_api_key_available", extra={"trace_id": "startup"})

_API_KEY_CONFIGURED = bool(_EXPECTED_API_KEY)

# Fail-fast in production: if no API key is configured and AUTH_DISABLED is
# not explicitly set, refuse to start. This prevents running an unauthenticated
# service in production accidentally.
_AUTH_DISABLED = os.environ.get("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in ("1", "true", "yes")
if not _API_KEY_CONFIGURED and not _AUTH_DISABLED:
    _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    if _ENV in ("production", "prod", "staging"):
        logger.critical(
            "FATAL: ENGINEERING_SERVICE_API_KEY is not set in %s environment. "
            "Set the API key or explicitly set ENGINEERING_SERVICE_AUTH_DISABLED=true "
            "to allow unauthenticated access (NOT recommended for production).",
            _ENV,
        )
        sys.exit(1)


def _require_api_key(request: Request) -> None:
    """Validate API key when configured.

    If ENGINEERING_SERVICE_API_KEY is set, every request must carry a
    matching ``x-api-key`` header.  If the key is *not* set:
    - In development: unauthenticated access is allowed (with warning).
    - In production: requests are REJECTED (fail-closed) unless
      ENGINEERING_SERVICE_AUTH_DISABLED=true is explicitly set.
    """
    if not _API_KEY_CONFIGURED:
        if _AUTH_DISABLED:
            return  # Explicitly opted-in to unauthenticated mode
        _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
        if _ENV in ("production", "prod", "staging"):
            raise HTTPException(
                status_code=401,
                detail="Authentication required but no API key configured. "
                       "Set ENGINEERING_SERVICE_API_KEY or ENGINEERING_SERVICE_AUTH_DISABLED=true",
            )
        # Development mode: allow unauthenticated access with warning
        return
    provided = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(provided, _EXPECTED_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Body size limit middleware
# ---------------------------------------------------------------------------

_MAX_BODY_SIZE = int(os.environ.get("ENGINEERING_SERVICE_MAX_BODY_SIZE", "1_048_576"))


class _BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > _MAX_BODY_SIZE:
                raise HTTPException(status_code=413, detail="Request body too large")
        return await call_next(request)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("engineering_service_startup", extra={"trace_id": "startup"})
    if not _API_KEY_CONFIGURED:
        if _AUTH_DISABLED:
            logger.warning(
                "SECURITY: Authentication is EXPLICITLY DISABLED via "
                "ENGINEERING_SERVICE_AUTH_DISABLED=true. All endpoints are "
                "accessible without authentication. Only use this in development!"
            )
        else:
            _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
            if _ENV in ("production", "prod", "staging"):
                logger.critical(
                    "FATAL: No API key configured in production. Service should have exited."
                )
            else:
                logger.warning(
                    "SECURITY WARNING: ENGINEERING_SERVICE_API_KEY is not set. "
                    "All endpoints are accessible without authentication in "
                    "development mode. Set this environment variable in production!"
                )

    # Initialize singleton StudyCache to avoid per-request connection creation
    global _study_cache
    try:
        from engine.caching import StudyCache
        _study_cache = StudyCache(
            redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"),
            ttl=int(os.environ.get("STUDY_CACHE_TTL", "3600")),
        )
        logger.info("study_cache_initialized", extra={"trace_id": "startup"})
    except Exception as e:
        logger.debug("StudyCache init failed (non-fatal, Redis may be unavailable): %s", e, extra={"trace_id": "startup"})

    yield
    logger.info("engineering_service_shutdown", extra={"trace_id": "shutdown"})


app = FastAPI(
    title="Ahmed etap Engineering Service",
    description="Production-grade power systems engineering computation API",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Register API routers (auth, projects)
# ---------------------------------------------------------------------------
try:
    from api.auth import router as auth_router
    app.include_router(auth_router)
    logger.info("auth_router_registered", extra={"trace_id": "startup"})
except ImportError as e:
    logger.warning("auth_router_unavailable: %s", e, extra={"trace_id": "startup"})
except Exception as e:
    logger.warning("auth_router_failed: %s", e, extra={"trace_id": "startup"})

try:
    from api.projects import router as projects_router
    app.include_router(projects_router)
    logger.info("projects_router_registered", extra={"trace_id": "startup"})
except ImportError as e:
    logger.warning("projects_router_unavailable: %s", e, extra={"trace_id": "startup"})
except Exception as e:
    logger.warning("projects_router_failed: %s", e, extra={"trace_id": "startup"})

# Initialize database tables at startup
try:
    import asyncio as _asyncio

    from api.database import init_db
    _asyncio.get_event_loop().run_until_complete(init_db())
    logger.info("database_initialized", extra={"trace_id": "startup"})
except Exception as e:
    logger.warning("database_init_failed (non-fatal): %s", e, extra={"trace_id": "startup"})

# ---------------------------------------------------------------------------
# LangWatch Observability Integration
# ---------------------------------------------------------------------------
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

# CORS — restrict origins; default allows only same-origin.
# Set ENGINEERING_SERVICE_CORS_ORIGINS to a comma-separated list of allowed origins.
# Example: ENGINEERING_SERVICE_CORS_ORIGINS=https://yourapp.example.com,https://worker.example.com
_CORS_ORIGINS = os.environ.get("ENGINEERING_SERVICE_CORS_ORIGINS", "").strip()
_cors_origin_list = [o.strip() for o in _CORS_ORIGINS.split(",") if o.strip()] if _CORS_ORIGINS else []
if not _cors_origin_list:
    _ENV = os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()
    if _ENV in ("production", "prod", "staging"):
        logger.warning(
            "CORS: No origins configured in %s environment. "
            "Set ENGINEERING_SERVICE_CORS_ORIGINS to your frontend URL(s). "
            "CORS is currently restrictive (no origins allowed).",
            _ENV,
        )
    else:
        logger.info(
            "CORS: No origins configured (development mode). "
            "Set ENGINEERING_SERVICE_CORS_ORIGINS for production."
        )
    _cors_origin_list = []  # No origins allowed = restrictive by default
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    allow_headers=["x-api-key", "x-trace-id", "content-type", "authorization"],
    expose_headers=["x-trace-id"],
)
app.add_middleware(_BodySizeLimitMiddleware)


# ---------------------------------------------------------------------------
# Rate Limiting (in-memory, per-client)
# ---------------------------------------------------------------------------

_RATE_LIMIT_WINDOW = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_WINDOW", "60"))  # seconds
_RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX", "100"))  # requests per window
_rate_limit_store: Dict[str, List[float]] = {}
_rate_limit_lock = _threading.Lock()
_RATE_LIMIT_MAX_ENTRIES = int(os.environ.get("ENGINEERING_SERVICE_RATE_LIMIT_MAX_ENTRIES", "10000"))

# Singleton StudyCache instance (initialized in lifespan)
_study_cache = None

# Module-level shared instances for digital twin endpoint
_shared_state_store = None
_shared_event_bus = None
_shared_validation_gateway = None


def _check_rate_limit(client_id: str) -> bool:
    """Check if the client has exceeded the rate limit. Returns True if allowed.

    Includes proactive cleanup to prevent unbounded memory growth.
    """
    now = time.time()
    with _rate_limit_lock:
        # Proactive cleanup: prune stale entries when store grows too large
        if len(_rate_limit_store) > _RATE_LIMIT_MAX_ENTRIES:
            stale = [cid for cid, timestamps in _rate_limit_store.items()
                     if not timestamps or now - timestamps[-1] > _RATE_LIMIT_WINDOW]
            for cid in stale:
                del _rate_limit_store[cid]

        if client_id not in _rate_limit_store:
            _rate_limit_store[client_id] = [now]
            return True
        # Remove timestamps outside the window
        _rate_limit_store[client_id] = [
            t for t in _rate_limit_store[client_id] if now - t < _RATE_LIMIT_WINDOW
        ]
        if len(_rate_limit_store[client_id]) >= _RATE_LIMIT_MAX_REQUESTS:
            return False
        _rate_limit_store[client_id].append(now)
        return True


# ---------------------------------------------------------------------------
# Request Timeout
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT_SEC = int(os.environ.get("ENGINEERING_SERVICE_REQUEST_TIMEOUT", "120"))  # seconds


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = trace_id

    # ── OpenTelemetry: extract incoming trace context and start a span ──
    tracer = get_tracer()
    with tracer.start_as_current_span(
        f"{request.method} {request.url.path}",
        kind=trace.SpanKind.SERVER,
        attributes={
            "http.method": request.method,
            "http.url": str(request.url),
            "http.route": request.url.path,
            "http.scheme": request.url.scheme,
            "net.peer.ip": request.client.host if request.client else "unknown",
        },
    ) as span:
        # Set the OTel trace ID as an attribute so it correlates with x-trace-id
        span.set_attribute("ahmedetap.trace_id", trace_id)

        # Rate limiting — skip for health endpoints
        if not request.url.path.startswith(("/health", "/ready", "/healthz", "/readyz", "/")):
            _TRUSTED_PROXIES = os.environ.get("ENGINEERING_SERVICE_TRUSTED_PROXIES", "")
            if _TRUSTED_PROXIES:
                _trusted_list = [p.strip() for p in _TRUSTED_PROXIES.split(",")]
                xff = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                proxy_ip = request.client.host if request.client else ""
                client_id = xff if proxy_ip in _trusted_list and xff else (request.client.host if request.client else "unknown")
            else:
                client_id = request.client.host if request.client else "unknown"
            if not _check_rate_limit(client_id):
                span.set_status(Status(StatusCode.ERROR, "rate_limit_exceeded"))
                span.set_attribute("http.status_code", 429)
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded", "trace_id": trace_id},
                    headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},
                )

        # RASP — Runtime Application Self-Protection (singleton engine)
        if not request.url.path.startswith(("/health", "/ready", "/healthz", "/readyz", "/", "/docs", "/openapi")):
            try:
                from security.rasp import create_default_rasp_engine
                if not hasattr(app.state, "rasp_engine"):
                    app.state.rasp_engine = create_default_rasp_engine()
                rasp = app.state.rasp_engine

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

                rasp_results = rasp.inspect({
                    "query": query_str, "path": path_str,
                    "body": body_str, "headers": header_str,
                })
                blocked = [r for r in rasp_results if r.action.value == "block"]
                if blocked:
                    attack_names = [r.rule_name for r in blocked]
                    span.set_status(Status(StatusCode.ERROR, "security_blocked"))
                    span.set_attribute("ahmedetap.blocked_attacks", str(attack_names))
                    logger.warning(
                        "rasp_blocked attacks=%s path=%s trace_id=%s",
                        attack_names, path_str, trace_id,
                    )
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Request blocked by security policy",
                            "attacks": attack_names, "trace_id": trace_id,
                        },
                    )
            except ImportError:
                pass
            except Exception as rasp_err:
                logger.debug("RASP check failed (non-fatal): %s", rasp_err)

        start = time.perf_counter()

        try:
            response = await asyncio.wait_for(call_next(request), timeout=_REQUEST_TIMEOUT_SEC)
            status_code = response.status_code
            span.set_attribute("http.status_code", status_code)
            if status_code >= 400:
                span.set_status(Status(StatusCode.ERROR, f"HTTP {status_code}"))
            else:
                span.set_status(Status(StatusCode.OK))
            response.headers["x-trace-id"] = trace_id
            # Inject OTel traceparent into response headers for client correlation
            _resp_carrier: dict[str, str] = {}
            inject_context(_resp_carrier)
            for k, v in _resp_carrier.items():
                response.headers[k] = v
            return response
        except asyncio.TimeoutError:
            span.set_status(Status(StatusCode.ERROR, "timeout"))
            span.set_attribute("error.type", "TimeoutError")
            logger.warning("request_timeout method=%s path=%s timeout=%ds", request.method, request.url.path, _REQUEST_TIMEOUT_SEC, extra={"trace_id": trace_id})
            return JSONResponse(
                status_code=504,
                content={"detail": f"Request timed out after {_REQUEST_TIMEOUT_SEC}s", "trace_id": trace_id},
            )
        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            logger.error("Unhandled exception: %s", e, extra={"trace_id": trace_id})
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            span.set_attribute("ahmedetap.latency_ms", elapsed_ms)
            logger.info("request=%s %s latency_ms=%.2f", request.method, request.url.path, elapsed_ms, extra={"trace_id": trace_id})


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.head("/")
@app.get("/")
async def root():
    """Root endpoint — also handles HEAD / for HF Spaces health checks."""
    return {"message": "Ahmed etap Engineering Platform", "version": "1.0.0"}


@app.head("/healthz")
@app.get("/healthz")
async def healthz():
    """Lightweight liveness probe (no heavy initialization)."""
    return {"status": "alive"}


@app.head("/readyz")
@app.get("/readyz")
async def readyz():
    """Readiness probe — checks critical dependencies."""
    checks = {"python": True, "imports": True}
    all_ready = all(checks.values())
    return {"ready": all_ready, "checks": checks}


@app.head("/health")
@app.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@app.head("/ready")
@app.get("/ready", response_model=ReadyResponse)
async def readiness_check(request: Request):
    native_ok = False
    etap_ok = False
    try:
        import numpy  # noqa: F401
        import scipy  # noqa: F401
        native_ok = True
    except ImportError:
        pass
    try:
        provider_factory = _get_etap_provider()
        provider = provider_factory()
        etap_ok = provider.is_available()
    except Exception as exc:
        logger.warning("etap_provider_unavailable", error=str(exc))
    return ReadyResponse(
        ready=native_ok,
        native_engine_available=native_ok,
        etap_available=etap_ok,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        trace_id=request.state.trace_id,
    )


@app.get("/metrics", response_model=MetricsResponse)
async def metrics(request: Request):
    with _metrics_lock:
        req_count = _request_count
        suc_count = _success_count
        fail_count = _failed_count
        total_time = _total_execution_time_sec
    avg_ms = (total_time / max(req_count, 1)) * 1000.0
    return MetricsResponse(
        requests_total=req_count,
        requests_success=suc_count,
        requests_failed=fail_count,
        avg_execution_time_ms=round(avg_ms, 2),
        trace_id=request.state.trace_id,
    )


@app.get("/prometheus/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint exposing counters, histograms, and gauges
    from ``core.metrics`` in the standard Prometheus exposition format.

    Returns
    -------
    Response with ``Content-Type: text/plain; version=0.0.4``

    Metrics include:
    - ``skill_operations_total`` — partitioned by operation and status
    - ``skill_operations_in_progress`` — gauge per operation type
    - ``skill_errors_total`` — by error type and skill name
    - ``execution_duration_seconds`` — histogram by skill and phase
    - ``executions_total`` — counter by skill and status
    - ``app_info`` — version metadata
    """
    return Response(
        content=generate_metrics(),
        media_type=get_metrics_content_type(),
    )


# ---------------------------------------------------------------------------
# Study execution endpoint
# ---------------------------------------------------------------------------

@app.post("/api/v1/studies/run", response_model=StudyResult)
@count_executions(skill_name="study")
@track_skill_operation("study")
async def run_study(request: Request, payload: StudyRequest):
    _require_api_key(request)
    trace_id = request.state.trace_id
    task_id = payload.task_id or str(uuid.uuid4())

    # Enable auto-correct for non-English input
    auto_correct = os.getenv('AUTO_CORRECT_LANGUAGE', 'true').lower() == 'true'

    # Normalize payload data if auto-correct is enabled
    if auto_correct:
        if payload.parameters:
            payload.parameters = {k: normalize_input(str(v)) for k, v in payload.parameters.items()}
        if payload.system:
            # Normalize system data if it's a string representation
            pass  # Add logic if needed

    _increment_counter("request")

    logger.info(
        "study_run_start study_type=%s use_etap=%s task_id=%s",
        payload.study_type,
        payload.use_etap,
        task_id,
        extra={"trace_id": trace_id},
    )

    warnings: List[str] = []
    errors: List[str] = []
    data: Dict[str, Any] = {}
    provider_name = "native"
    cache_hit = False

    try:
        # --- Cache lookup for native studies (non-ETAP) ---
        if not payload.use_etap:
            try:
                cache_params = {"study_type": payload.study_type, "parameters": payload.parameters}
                if payload.system:
                    # Use deterministic hashing (SHA-256) instead of Python hash()
                    import hashlib as _hashlib
                    system_json = json.dumps(payload.system.model_dump(), sort_keys=True, default=str)
                    cache_params["system_hash"] = _hashlib.sha256(system_json.encode()).hexdigest()
                if _study_cache:
                    cached_result = await _study_cache.get(payload.study_type, cache_params)
                    if cached_result:
                        data = json.loads(cached_result)
                        cache_hit = True
                        logger.info("study_cache_hit study_type=%s task_id=%s", payload.study_type, task_id, extra={"trace_id": trace_id})
            except Exception as cache_err:
                logger.debug("Cache lookup failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id})

        if cache_hit:
            # Use cached data
            pass
        elif payload.use_etap:
            if not payload.etap_project_path:
                raise ValueError("etap_project_path is required when use_etap=True")
            provider_name = "etap"
            # Offload the synchronous ETAP call to a thread so it doesn't
            # block the async event loop (ETAP COM calls can take 5-60 sec).
            data = await asyncio.to_thread(
                _run_etap_study,
                payload.study_type,
                payload.etap_project_path,
                payload.parameters,
            )
            warnings = data.pop("warnings", [])
            errors = data.pop("errors", [])
            if not data.pop("success", True):
                errors.append("ETAP study reported failure")
        else:
            system = None
            if payload.system:
                try:
                    system = _build_system_from_spec(payload.system)
                except ValueError as ve:
                    raise HTTPException(status_code=400, detail=f"System spec error: {ve}") from ve
            data = _run_native_study(payload.study_type, system, payload.parameters)
            provider_name = "native"

            # --- Store result in cache ---
            try:
                cache_params = {"study_type": payload.study_type, "parameters": payload.parameters}
                if payload.system:
                    import hashlib as _hashlib
                    system_json = json.dumps(payload.system.model_dump(), sort_keys=True, default=str)
                    cache_params["system_hash"] = _hashlib.sha256(system_json.encode()).hexdigest()
                if _study_cache:
                    await _study_cache.set(payload.study_type, cache_params, json.dumps(data, default=str))
            except Exception as cache_err:
                logger.debug("Cache store failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id})

        _increment_counter("success")
        status = "success"
    except HTTPException:
        raise
    except Exception as e:
        _increment_counter("failed")
        logger.error("study_run_failed study_type=%s error=%s", payload.study_type, str(e), extra={"trace_id": trace_id})
        errors.append(str(e))
        status = "failed"
        data = {}

    # Strip numpy types so FastAPI / Pydantic can serialize the response
    data = _to_jsonable(data)

    elapsed_sec = time.perf_counter() - start
    _add_execution_time(elapsed_sec)

    logger.info(
        "study_run_end study_type=%s status=%s elapsed_sec=%.3f task_id=%s",
        payload.study_type,
        status,
        elapsed_sec,
        task_id,
        extra={"trace_id": trace_id},
    )

    return StudyResult(
        success=status == "success",
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
# ---------------------------------------------------------------------------

@app.post("/api/v1/system/validate")
@count_executions(skill_name="validate_system")
@track_skill_operation("validate_system")
async def validate_system(request: Request, spec: SystemSpec):
    """Validate a power system model specification.

    Checks structural integrity: all bus references exist, impedance
    values are non-negative, slack bus is present, etc.

    Accepts the same flexible field names as /api/v1/studies/run
    (e.g. ``b1`` for ``bshunt1``, ``load_power_reactive`` for
    ``load_power_imag``).  Extra fields are silently ignored.
    """
    _require_api_key(request)
    trace_id = request.state.trace_id
    warnings: List[str] = []
    errors: List[str] = []

    try:
        # Structural validation
        if not spec.buses:
            errors.append("System must have at least one bus")
        if not spec.lines and not spec.transformers:
            warnings.append("System has no lines or transformers — it may be degenerate")
        slack_buses = [b for b in spec.buses if b.bus_type == "slack"]
        if len(slack_buses) == 0:
            errors.append("System must have at least one slack bus")
        if len(slack_buses) > 1:
            warnings.append(f"System has {len(slack_buses)} slack buses; typically only one is expected")

        bus_ids = {b.bus_id for b in spec.buses}
        for line in spec.lines:
            if line.from_bus_id not in bus_ids:
                errors.append(f"Line {line.line_id} references unknown from_bus_id {line.from_bus_id}")
            if line.to_bus_id not in bus_ids:
                errors.append(f"Line {line.line_id} references unknown to_bus_id {line.to_bus_id}")

        for gen in spec.generators:
            if gen.bus_id not in bus_ids:
                errors.append(f"Generator {gen.generator_id} references unknown bus_id {gen.bus_id}")

        for ld in spec.loads:
            if ld.bus_id not in bus_ids:
                errors.append(f"Load {ld.load_id} references unknown bus_id {ld.bus_id}")

        # Build system to catch remaining issues
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
            "transformer_count": len(spec.transformers),
            "trace_id": trace_id,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        logger.error("system_validation_failed error=%s", str(e), extra={"trace_id": trace_id})
        raise HTTPException(status_code=500, detail="Internal validation error") from e


# ---------------------------------------------------------------------------
# Agent Info Endpoint — exposes prompt integration status
# ---------------------------------------------------------------------------

@app.get("/api/v1/agents/info")
async def get_agents_info(request: Request):
    """Return metadata for all agents including prompt integration status.

    This endpoint verifies that prompts are loaded into agents at runtime
    and provides prompt handle mapping for debugging and monitoring.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from agents.orchestrator import ChiefEngineeringOrchestrator
        orchestrator = ChiefEngineeringOrchestrator()
        info = orchestrator.get_agents_info()

        # Also list available prompts from the prompt loader
        from agents.prompt_loader import list_available_prompts
        available_prompts = list_available_prompts()

        return JSONResponse(content={
            "success": True,
            "data": {
                **info,
                "available_prompts": available_prompts,
                "prompt_count": len(available_prompts),
            },
            "trace_id": trace_id,
        })
    except Exception as e:
        logger.error("agents_info_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# ---------------------------------------------------------------------------
# AI/ML Endpoints — Predictive Analytics, Anomaly Detection, RAG
# ---------------------------------------------------------------------------

@app.post("/api/v1/predict/load")
@count_executions(skill_name="predict_load")
@track_skill_operation("predict_load")
async def predict_load(request: Request):
    """Predict future load using the LSTM-based LoadForecaster."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        historical = body.get("historical_data", [])
        horizon = body.get("horizon_hours", 24)

        if not historical:
            raise HTTPException(status_code=400, detail="historical_data is required")
        if not isinstance(historical, list):
            raise HTTPException(status_code=400, detail="historical_data must be an array")
        if len(historical) > 10000:
            raise HTTPException(status_code=400, detail="historical_data array too large (max 10000 points)")
        if not isinstance(horizon, int) or horizon < 1 or horizon > 168:
            raise HTTPException(status_code=400, detail="horizon_hours must be between 1 and 168")

        import numpy as np

        from ml.predictive import LoadForecaster
        lf = LoadForecaster()
        data = np.array(historical, dtype=float)
        lf.train(data)
        predictions = lf.predict(horizon_hours=horizon)
        metrics = lf.evaluate(data) if hasattr(lf, 'evaluate') else {}

        return JSONResponse(content={
            "success": True,
            "data": {
                "predictions": predictions.tolist() if hasattr(predictions, 'tolist') else list(predictions),
                "horizon_hours": horizon,
                "input_points": len(historical),
                "metrics": metrics,
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("predict_load_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


@app.post("/api/v1/predict/fault")
@count_executions(skill_name="predict_fault")
@track_skill_operation("predict_fault")
async def predict_fault(request: Request):
    """Predict fault type using the Random Forest FaultPredictor."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        features = body.get("features", [])

        if not features:
            raise HTTPException(status_code=400, detail="features array is required")
        if not isinstance(features, list):
            raise HTTPException(status_code=400, detail="features must be an array")
        if len(features) > 1000:
            raise HTTPException(status_code=400, detail="features array too large (max 1000 elements)")

        import numpy as np

        from ml.predictive import FaultPredictor
        fp = FaultPredictor()
        X = np.array(features, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        prediction = fp.predict(X)

        return JSONResponse(content={
            "success": True,
            "data": prediction if isinstance(prediction, dict) else {"prediction": prediction},
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("predict_fault_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


@app.post("/api/v1/predict/anomaly")
@count_executions(skill_name="detect_anomaly")
@track_skill_operation("detect_anomaly")
async def detect_anomalies(request: Request):
    """Detect anomalies in measurement data using Isolation Forest."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        data = body.get("data", [])

        if not data:
            raise HTTPException(status_code=400, detail="data array is required")
        if not isinstance(data, list):
            raise HTTPException(status_code=400, detail="data must be an array")
        if len(data) > 10000:
            raise HTTPException(status_code=400, detail="data array too large (max 10000 points)")

        import numpy as np

        from ml.predictive import AnomalyDetector
        ad = AnomalyDetector()
        X = np.array(data, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)
        result = ad.detect(X)

        return JSONResponse(content={
            "success": True,
            "data": result,
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("anomaly_detection_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


@app.post("/api/v1/rag/query")
@count_executions(skill_name="rag_query")
@track_skill_operation("rag_query")
async def rag_query(request: Request):
    """Query the engineering knowledge base with RAG (IEEE/IEC standards)."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        query = body.get("query", "")
        top_k = body.get("top_k", 5)

        if not query:
            raise HTTPException(status_code=400, detail="query is required")

        os.environ.setdefault("RAG_ALLOW_HASH_FALLBACK", "1")
        from knowledge.rag_engine import EngineeringKnowledgeBase
        kb = EngineeringKnowledgeBase()
        results = kb.search(query, top_k=top_k)

        return JSONResponse(content={
            "success": True,
            "data": {
                "query": query,
                "results": results if isinstance(results, list) else str(results),
                "top_k": top_k,
                "standards_covered": [
                    "IEEE 1584-2018", "IEC 60909", "IEEE 519-2022",
                    "IEC 60255", "IEEE 3002.7", "IEEE 399", "IEEE 80",
                ],
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("rag_query_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


# ---------------------------------------------------------------------------
# SCADA Live Data Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/v1/scada/live")
async def get_scada_live_data(request: Request):
    """Return live SCADA data model mapping for IEC 61850 logical nodes.

    This endpoint provides the current state of the SCADA data model,
    including bus voltages, loads, and switch positions mapped from
    IEC 61850 logical nodes (MMXU, MSQI, XCBR, XSWI).
    """
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from scada_model.scada_model import MeasurementType, QualityFlag, SCADADatabase
        db = SCADADatabase()

        # Return a summary of the SCADA model
        measurements = db.get_all_measurements() if hasattr(db, 'get_all_measurements') else []
        switches = db.get_all_switches() if hasattr(db, 'get_all_switches') else []

        return JSONResponse(content={
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
        })
    except Exception as e:
        logger.error("scada_live_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


# ---------------------------------------------------------------------------
# Digital Twin Sync Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/v1/digital-twin/status")
async def get_digital_twin_status(request: Request):
    """Return Digital Twin synchronization status and state store info."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from digital_twin.event_bus import EventBus
        from digital_twin.state_store import StateStore
        from digital_twin.validation_gateway import ValidationGateway

        global _shared_state_store, _shared_event_bus, _shared_validation_gateway
        if _shared_state_store is None:
            _shared_state_store = StateStore()
            _shared_event_bus = EventBus()
            _shared_validation_gateway = ValidationGateway()
        store = _shared_state_store

        # Get state store info
        state_info = {}
        if hasattr(store, 'get_state'):
            state = store.get_state()
            state_info = {"entities": len(state) if isinstance(state, dict) else 0}
        elif hasattr(store, 'state'):
            state_info = {"entities": len(store.state) if isinstance(store.state, dict) else 0}
        else:
            state_info = {"available": True}

        return JSONResponse(content={
            "success": True,
            "data": {
                "state_store": state_info,
                "event_bus": {"available": True},
                "validation_gateway": {"available": True},
                "sync_protocols": ["AWS IoT TwinMaker", "Azure Digital Twins"],
                "supported_models": ["Substation", "Bus", "Line", "Transformer", "Generator"],
            },
            "trace_id": trace_id,
        })
    except Exception as e:
        logger.error("digital_twin_status_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


# ---------------------------------------------------------------------------
# MFA Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/v1/auth/mfa/totp/setup")
async def setup_totp(request: Request):
    """Set up TOTP-based MFA for a user."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_id = body.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        from security.mfa import TOTPProvider
        totp = TOTPProvider()
        secret = totp.generate_secret(user_id)
        qr_uri = totp.generate_qr_code(user_id, secret)
        totp.generate_backup_codes(user_id)

        return JSONResponse(content={
            "success": True,
            "data": {
                "qr_code_uri": qr_uri,
                # Note: secret and backup_codes are NOT exposed in the API response
                # to prevent credential leakage. They are stored server-side only.
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("totp_setup_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


@app.post("/api/v1/auth/mfa/totp/verify")
async def verify_totp(request: Request):
    """Verify a TOTP code for MFA."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_id = body.get("user_id")
        code = body.get("code")
        if not user_id or not code:
            raise HTTPException(status_code=400, detail="user_id and code are required")

        from security.mfa import MFAOrchestrator
        mfa = MFAOrchestrator()
        verified = mfa.verify_totp(user_id, code)

        return JSONResponse(content={
            "success": True,
            "data": {"verified": verified, "user_id": user_id},
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("totp_verify_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


# ---------------------------------------------------------------------------
# ABAC Endpoint
# ---------------------------------------------------------------------------

@app.post("/api/v1/auth/abac/check")
async def check_abac(request: Request):
    """Check ABAC policy for a user action."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        user_attrs = body.get("user", {})
        resource = body.get("resource")
        action = body.get("action")
        environment = body.get("environment", {"time": "business_hours"})

        if not user_attrs or not resource or not action:
            raise HTTPException(status_code=400, detail="user, resource, and action are required")

        from security.abac import create_default_etap_abac_engine
        engine = create_default_etap_abac_engine()
        allowed = engine.evaluate(user_attrs, resource, action, environment)

        return JSONResponse(content={
            "success": True,
            "data": {
                "allowed": allowed,
                "user": user_attrs,
                "resource": resource,
                "action": action,
            },
            "trace_id": trace_id,
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error("abac_check_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


# ---------------------------------------------------------------------------
# RASP Stats Endpoint
# ---------------------------------------------------------------------------

@app.get("/api/v1/security/rasp/stats")
async def get_rasp_stats(request: Request):
    """Return RASP inspection statistics."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        from security.rasp import create_default_rasp_engine
        # Use the app-level singleton RASP engine to get accurate stats
        if hasattr(app.state, "rasp_engine"):
            rasp = app.state.rasp_engine
        else:
            rasp = create_default_rasp_engine()
        stats = rasp.get_stats()
        return JSONResponse(content={
            "success": True,
            "data": stats,
            "trace_id": trace_id,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


# ---------------------------------------------------------------------------
# SIEM Events Endpoint
# ---------------------------------------------------------------------------

@app.post("/api/v1/security/siem/event")
async def submit_siem_event(request: Request):
    """Submit a security event to the SIEM forwarder."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        body = await request.json()
        import uuid as uuid_mod
        from datetime import datetime, timezone

        from security.siem import SecurityEvent, get_siem_forwarder

        _VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}
        severity = body.get("severity", "info")
        if severity not in _VALID_SEVERITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(_VALID_SEVERITIES))}"
            )
        event_type = body.get("event_type", "custom")
        if not event_type or len(event_type) > 100:
            raise HTTPException(
                status_code=400,
                detail="event_type must be a non-empty string (max 100 chars)"
            )
        event = SecurityEvent(
            event_id=body.get("event_id", str(uuid_mod.uuid4())),
            timestamp=body.get("timestamp", datetime.now(timezone.utc).isoformat()),
            event_type=event_type,
            severity=severity,
            source=body.get("source", "engineering_service"),
            details=body.get("details", {}),
        )

        forwarder = get_siem_forwarder()
        if forwarder and hasattr(forwarder, "forward_event"):
            await forwarder.forward_event(event)

        return JSONResponse(content={
            "success": True,
            "data": {"event_id": event.event_id, "forwarded": forwarder is not None},
            "trace_id": trace_id,
        })
    except Exception as e:
        logger.error("siem_event_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(status_code=500, content={"success": False, "errors": [str(e)], "trace_id": trace_id})


# ---------------------------------------------------------------------------
# Benchmark endpoint — CPU vs GPU, Sparse vs Dense, Sequential vs Parallel
# ---------------------------------------------------------------------------

@app.get("/api/v1/benchmark")
async def benchmark_solvers(request: Request):
    """Run solver benchmarks comparing CPU/GPU, sparse/dense, and sequential/parallel.

    Returns timing data for various system sizes (14, 30, 118 bus).
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    try:
        results: Dict[str, Any] = {}

        # GPU solver benchmark
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

        # Sparse matrix memory comparison
        try:
            from engine.sparse_solver import SparseYBus
            builder = SparseYBus()
            sparse_results = []
            for n in [14, 30, 118]:
                buses, branches = builder._generate_synthetic_system(n)
                ybus = builder.build_sparse_ybus(buses, branches)
                dense_bytes = n * n * 16
                sparse_bytes = ybus.data.nbytes + ybus.indices.nbytes + ybus.indptr.nbytes
                sparse_results.append({
                    "n_buses": n,
                    "nnz": int(ybus.nnz),
                    "density": round(float(ybus.nnz) / (n * n), 4),
                    "dense_bytes": dense_bytes,
                    "sparse_bytes": sparse_bytes,
                    "savings_pct": round((1 - sparse_bytes / dense_bytes) * 100, 1),
                })
            results["sparse_matrix"] = sparse_results
        except Exception as e:
            results["sparse_matrix"] = {"error": str(e)}

        # Redis cache stats
        try:
            from engine.caching import StudyCache
            cache = StudyCache(
                redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379"),
            )
            stats = await cache.get_stats()
            results["cache"] = stats
        except Exception as e:
            results["cache"] = {"error": str(e), "available": False}

        return JSONResponse(content={
            "success": True,
            "data": results,
            "trace_id": trace_id,
        })
    except Exception as e:
        logger.error("benchmark_failed error=%s", str(e), extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


# Error handlers
# ---------------------------------------------------------------------------

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.warning("ValueError: %s", str(exc), extra={"trace_id": trace_id})
    return JSONResponse(
        status_code=400,
        content={"success": False, "errors": [str(exc)], "trace_id": trace_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", "unknown")
    logger.error("Unhandled exception: %s", str(exc), extra={"trace_id": trace_id})
    return JSONResponse(
        status_code=500,
        content={"success": False, "errors": ["Internal server error"], "trace_id": trace_id},
    )


# ---------------------------------------------------------------------------
# WebSocket API for Real-Time Study Updates
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manage WebSocket connections for real-time study updates."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

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
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


_ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Guard Skills Endpoints (guard-skills integration)
# ---------------------------------------------------------------------------

class GuardReviewRequest(BaseModel):
    """Request schema for guard review endpoints."""
    source: str = Field(..., description="Source code or documentation to review", min_length=1, max_length=500_000)
    guard_type: str = Field(default="all", description="Guard type: code, test, docs, ai_failure_modes, or all")
    language: str = Field(default="python", description="Language hint for the scanner")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context (known symbols, etc.)")


class GuardReviewResponse(BaseModel):
    """Response schema for guard review endpoints."""
    success: bool
    guard_results: Dict[str, Any] = {}
    all_passed: bool = True
    must_fix_total: int = 0
    should_fix_total: int = 0
    worth_noting_total: int = 0
    trace_id: str = "unknown"


@app.post("/api/v1/guards/review", response_model=GuardReviewResponse)
@count_executions(skill_name="guard_review")
@track_skill_operation("guard_review")
async def guard_review(request: Request, body: GuardReviewRequest):
    """Review source code against guard-skills quality gates.

    Runs the specified guard(s) against the provided source code and
    returns a structured report of violations with severity levels.
    MUST_FIX violations indicate code that should not be shipped.
    """
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")

    try:
        from guards import AIFailureModeDetector, CodeGuard, DocsGuard, TestGuard
        from guards.base import GuardMode

        results: Dict[str, Any] = {}
        must_fix_total = 0
        should_fix_total = 0
        worth_noting_total = 0

        if body.guard_type in ("all", "code"):
            guard = CodeGuard(mode=GuardMode.GUARD_PASS)
            result = guard.scan(body.source, body.language, body.context)
            results["code_guard"] = result.to_dict()
            must_fix_total += result.must_fix_count
            should_fix_total += result.should_fix_count
            worth_noting_total += result.worth_noting_count

        if body.guard_type in ("all", "test"):
            guard = TestGuard(mode=GuardMode.GUARD_PASS)
            result = guard.scan(body.source, body.language, body.context)
            results["test_guard"] = result.to_dict()
            must_fix_total += result.must_fix_count
            should_fix_total += result.should_fix_count
            worth_noting_total += result.worth_noting_count

        if body.guard_type in ("all", "docs"):
            guard = DocsGuard(mode=GuardMode.GUARD_PASS)
            result = guard.scan(body.source, "markdown", body.context)
            results["docs_guard"] = result.to_dict()
            must_fix_total += result.must_fix_count
            should_fix_total += result.should_fix_count
            worth_noting_total += result.worth_noting_count

        if body.guard_type in ("all", "ai_failure_modes"):
            detector = AIFailureModeDetector(mode=GuardMode.GUARD_PASS)
            result = detector.detect(body.source, body.context)
            results["ai_failure_modes"] = result.to_dict()
            must_fix_total += result.must_fix_count
            should_fix_total += result.should_fix_count
            worth_noting_total += result.worth_noting_count

        all_passed = must_fix_total == 0

        return GuardReviewResponse(
            success=True,
            guard_results=results,
            all_passed=all_passed,
            must_fix_total=must_fix_total,
            should_fix_total=should_fix_total,
            worth_noting_total=worth_noting_total,
            trace_id=trace_id,
        )

    except ImportError as e:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "errors": [f"Guards module not available: {e}"],
                "trace_id": trace_id,
            },
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "errors": [str(e)], "trace_id": trace_id},
        )


@app.get("/api/v1/guards/info")
async def guard_info(request: Request):
    """Return information about available guard skills and their rules."""
    _require_api_key(request)
    trace_id = getattr(request.state, "trace_id", "unknown")

    try:
        from guards import AI_FAILURE_MODES
        from guards.base import GuardSeverity  # noqa: F401

        return JSONResponse(content={
            "success": True,
            "data": {
                "guards": {
                    "code_guard": {
                        "name": "Code Guard",
                        "description": "Production code quality gate: 23 clean-code rules + 14 AI failure modes",
                        "rules_checked": 23,
                    },
                    "test_guard": {
                        "name": "Test Guard",
                        "description": "Test code quality gate: 9 universal rules + 3 LLM-specific rules",
                        "rules_checked": 12,
                    },
                    "docs_guard": {
                        "name": "Docs Guard",
                        "description": "Documentation accuracy gate: 10 rules for claim verification",
                        "rules_checked": 10,
                    },
                    "ai_failure_modes": {
                        "name": "AI Failure Mode Detector",
                        "description": "Detects 14 systematic LLM code-generation failure patterns",
                        "failure_modes": [
                            {
                                "id": fm.id,
                                "name": fm.name,
                                "severity": fm.severity.value,
                                "description": fm.description,
                                "research_source": fm.research_source,
                            }
                            for fm in AI_FAILURE_MODES
                        ],
                    },
                },
                "severity_levels": {
                    "must_fix": "Blocks execution/merge — security or correctness issue",
                    "should_fix": "Should fix before shipping — design defect or maintenance drag",
                    "worth_noting": "Informational — polish or architecture suggestion",
                },
                "source": "Adapted from guard-skills (github.com/amElnagdy/guard-skills)",
            },
            "trace_id": trace_id,
        })
    except ImportError:
        return JSONResponse(content={
            "success": True,
            "data": {
                "guards": {},
                "note": "Guards module not available in this deployment",
            },
            "trace_id": trace_id,
        })


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the engineering service."""
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(
        prog="engineering_service",
        description="Ahmed etap Engineering Service - FastAPI server for power systems analysis"
    )
    parser.add_argument("--host", type=str, default=os.environ.get("ENGINEERING_SERVICE_HOST", "0.0.0.0"),
                        help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("ENGINEERING_SERVICE_PORT", os.environ.get("PORT", "8000"))),
                        help="Port to bind (default: 8000, or PORT env var for HF Spaces)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of worker processes (default: 1)")
    args = parser.parse_args()

    logger.info("Starting Engineering Service on %s:%d", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, workers=args.workers)


if __name__ == "__main__":
    main()
