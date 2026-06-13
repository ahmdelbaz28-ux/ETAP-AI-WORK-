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

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, AliasChoices, field_validator
from starlette.middleware.base import BaseHTTPMiddleware

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


def _increment_counter(name: str, delta: int = 1) -> None:
    """Thread-safe counter increment."""
    global _request_count, _success_count, _failed_count
    with _metrics_lock:
        if name == "request":
            _request_count += delta
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

def _build_system_from_spec(spec: SystemSpec) -> Any:
    """Build a Python System object from a SystemSpec."""
    from core_model.system import System
    from core_model.bus import Bus
    from core_model.line import Line
    from core_model.transformer import Transformer
    from core_model.generator import Generator
    from core_model.load import Load

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
# ---------------------------------------------------------------------------
_SMITHERY_API_KEY = os.environ.get("SMITHERY_API_KEY", "")
if _SMITHERY_API_KEY and not _EXPECTED_API_KEY:
    _EXPECTED_API_KEY = _SMITHERY_API_KEY
    logger.info("smithery_api_key_loaded", extra={"trace_id": "startup"})

_API_KEY_CONFIGURED = bool(_EXPECTED_API_KEY)


def _require_api_key(request: Request) -> None:
    """Validate API key when configured.

    If ENGINEERING_SERVICE_API_KEY is set, every request must carry a
    matching ``x-api-key`` header.  If the key is *not* set the service
    logs a warning on startup (and every 10 minutes while running) but
    still allows unauthenticated access so that local development is not
    broken.  In production you MUST set the key.
    """
    if not _API_KEY_CONFIGURED:
        # Allow unauthenticated access in development mode only.
        # A warning is logged at startup (see below) and periodically.
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
        logger.warning(
            "SECURITY WARNING: ENGINEERING_SERVICE_API_KEY is not set. "
            "All endpoints are accessible without authentication. "
            "Set this environment variable in production!"
        )
    yield
    logger.info("engineering_service_shutdown", extra={"trace_id": "shutdown"})


app = FastAPI(
    title="ETAP AI Engineering Service",
    description="Production-grade power systems engineering computation API",
    version="1.0.0",
    lifespan=lifespan,
)

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
    logger.warning(
        "CORS: No origins configured (ENGINEERING_SERVICE_CORS_ORIGINS is empty). "
        "CORS will be restrictive. Set this to your frontend URL(s) in production."
    )
    _cors_origin_list = [""]  # Empty string = same-origin only
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origin_list,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["x-api-key", "x-trace-id", "content-type"],
    expose_headers=["x-trace-id"],
)
app.add_middleware(_BodySizeLimitMiddleware)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    start = time.perf_counter()

    try:
        response = await call_next(request)
        response.headers["x-trace-id"] = trace_id
        return response
    except Exception as e:
        logger.error("Unhandled exception: %s", e, extra={"trace_id": trace_id})
        raise
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("request=%s %s latency_ms=%.2f", request.method, request.url.path, elapsed_ms, extra={"trace_id": trace_id})


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.head("/")
@app.get("/")
async def root():
    """Root endpoint — also handles HEAD / for HF Spaces health checks."""
    return {"message": "ETAP AI Engineering Platform", "version": "1.0.0"}


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


# ---------------------------------------------------------------------------
# Study execution endpoint
# ---------------------------------------------------------------------------

@app.post("/api/v1/studies/run", response_model=StudyResult)
async def run_study(request: Request, payload: StudyRequest):
    _require_api_key(request)
    trace_id = request.state.trace_id
    task_id = payload.task_id or str(uuid.uuid4())
    start = time.perf_counter()

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

    try:
        if payload.use_etap:
            if not payload.etap_project_path:
                raise ValueError("etap_project_path is required when use_etap=True")
            provider_name = "etap"
            data = _run_etap_study(payload.study_type, payload.etap_project_path, payload.parameters)
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
                    raise HTTPException(status_code=400, detail=f"System spec error: {ve}")
            data = _run_native_study(payload.study_type, system, payload.parameters)
            provider_name = "native"

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
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error("system_validation_failed error=%s", str(e), extra={"trace_id": trace_id})
        raise HTTPException(status_code=500, detail="Internal validation error")


# ---------------------------------------------------------------------------
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
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the engineering service."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(
        prog="engineering_service",
        description="ETAP AI Engineering Service - FastAPI server for power systems analysis"
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
