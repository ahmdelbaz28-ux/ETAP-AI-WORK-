"""
Study Execution API Router
==========================
Handles all power system study execution endpoints.
Separated from main engineering service for better modularity.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from api.dependencies import get_api_key
from core.metrics import count_executions, track_skill_operation
from engine.caching import StudyCache

router = APIRouter(prefix="/api/v1/studies", tags=["studies"])

# Import from core models
from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from core_model.transformer import Transformer


class BusSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bus_id: int
    voltage_magnitude: float = Field(
        default=1.0, validation_alias=AliasChoices("voltage_magnitude", "vm")
    )
    voltage_angle: float = Field(default=0.0, validation_alias=AliasChoices("voltage_angle", "va"))
    load_power_real: float = Field(
        default=0.0, validation_alias=AliasChoices("load_power_real", "p_load", "pd")
    )
    load_power_imag: float = Field(
        default=0.0,
        validation_alias=AliasChoices("load_power_imag", "load_power_reactive", "q_load", "qd"),
    )
    generation_power_real: float = Field(
        default=0.0, validation_alias=AliasChoices("generation_power_real", "power_real", "pg")
    )
    generation_power_imag: float = Field(
        default=0.0, validation_alias=AliasChoices("generation_power_imag", "power_reactive", "qg")
    )
    bus_type: str = "pq"
    base_kv: float | None = None
    q_min: float = Field(
        default=-999.0, validation_alias=AliasChoices("q_min", "min_power_reactive", "min_q")
    )
    q_max: float = Field(
        default=999.0, validation_alias=AliasChoices("q_max", "max_power_reactive", "max_q")
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
        default=0.02, validation_alias=AliasChoices("bshunt1", "b1", "bshunt", "susceptance")
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
        default=0.0, validation_alias=AliasChoices("phase_shift_deg", "phase_shift")
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
        default=0.0, validation_alias=AliasChoices("internal_voltage_ang_deg", "voltage_angle")
    )
    power_real: float | None = Field(
        default=None, validation_alias=AliasChoices("power_real", "pg")
    )
    power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("power_reactive", "qg")
    )
    max_power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("max_power_reactive", "q_max")
    )
    min_power_reactive: float | None = Field(
        default=None, validation_alias=AliasChoices("min_power_reactive", "q_min")
    )


class LoadSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    load_id: int
    bus_id: int
    p_mw: float = Field(
        default=0.0, validation_alias=AliasChoices("p_mw", "power_real", "load_power_real")
    )
    q_mvar: float = Field(
        default=0.0,
        validation_alias=AliasChoices("q_mvar", "power_reactive", "load_power_reactive"),
    )
    constant_impedance: bool = False


class SystemSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_mva: float = Field(
        default=100.0, validation_alias=AliasChoices("base_mva", "sbase", "base_mva")
    )
    buses: List[BusSpec] = Field(default_factory=list)
    lines: List[LineSpec] = Field(
        default_factory=list, validation_alias=AliasChoices("lines", "branches")
    )
    transformers: List[TransformerSpec] = Field(default_factory=list)
    generators: List[GeneratorSpec] = Field(default_factory=list)
    loads: List[LoadSpec] = Field(default_factory=list)


class StudyRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    study_type: str = Field(..., description="Type of study to run")
    system: SystemSpec | None = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    task_id: str | None = None
    use_etap: bool = Field(
        default=False, description="If True, route to ETAP provider instead of native engine"
    )
    etap_project_path: str | None = None

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
            # ETAP Expert skill — 6-step workflow with Format A/B/C/D responses
            "etap_expert",
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
    task_id: str | None = None
    study_type: str = ""
    provider: str = "native"


def _to_jsonable(obj: Any) -> Any:
    """Recursively convert numpy types (and other engine outputs) to native
    Python primitives that FastAPI / Pydantic can serialize as JSON."""
    import numpy as np

    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        # Reject nan/inf which are not valid JSON
        if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
            return None
        return obj
    if isinstance(obj, complex):
        re, im = obj.real, obj.imag
        return {"re": _to_jsonable(re), "im": _to_jsonable(im)}
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


def _build_system_from_spec(spec: SystemSpec) -> Any:
    """Build a Python System object from a SystemSpec."""
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
                "2": complex(
                    g.r2 if g.r2 is not None else g.r1, g.x2 if g.x2 is not None else g.x1
                ),
                "0": complex(
                    g.r0 if g.r0 is not None else g.r1, g.x0 if g.x0 is not None else g.x1
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


_STUDIES_REQUIRING_SYSTEM = {
    "load_flow",
    "short_circuit",
    "fault",
    "protection_coordination",
    "coordination",
    "motor_starting",
}


def _run_native_study(
    study_type: str, system: Any | None, parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a study using the native PowerSystemEngine."""
    if study_type in _STUDIES_REQUIRING_SYSTEM and system is None:
        raise ValueError(f"study_type '{study_type}' requires a 'system' to be provided")

    # ETAP Expert skill — 6-step workflow with Format A/B/C/D responses.
    # Routes to the dedicated ETAPExpertAgent instead of the numerical engine.
    if study_type == "etap_expert":
        from agents.etap_expert_agent import ETAPExpertAgent

        agent = ETAPExpertAgent()
        question = str(parameters.get("question", "")).strip()
        if not question:
            raise ValueError("'question' field is required for study_type='etap_expert'")
        return agent.answer(question)

    from engine.engine import PowerSystemEngine

    engine = PowerSystemEngine(system)

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
                f"arc_flash requires: {', '.join(required)} (missing: {', '.join(missing)})"
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
    else:
        raise ValueError(f"Unsupported native study type: {study_type}")


@router.post("/run", response_model=StudyResult)
@count_executions(skill_name="study")
@track_skill_operation("study")
async def run_study(request: Request, payload: StudyRequest, _: str = Depends(get_api_key)):
    trace_id = getattr(request.state, "trace_id", "unknown")
    task_id = payload.task_id or str(uuid.uuid4())
    start = time.perf_counter()

    from core.bootstrap import _add_execution_time, _increment_counter

    _increment_counter("request")

    from logging import getLogger

    logger = getLogger("engineering_service")
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
        # Initialize study cache if needed
        study_cache = None
        try:
            study_cache = StudyCache(
                redis_url="redis://localhost:6379",
                ttl=3600,
            )
        except Exception:
            logger.debug("StudyCache init failed (non-fatal)")

        # --- Cache lookup for native studies (non-ETAP) ---
        if not payload.use_etap:
            try:
                cache_params = {"study_type": payload.study_type, "parameters": payload.parameters}
                if payload.system:
                    import hashlib as _hashlib

                    system_json = json.dumps(
                        payload.system.model_dump(), sort_keys=True, default=str
                    )
                    cache_params["system_hash"] = _hashlib.sha256(system_json.encode()).hexdigest()
                if study_cache:
                    cached_result = await study_cache.get(payload.study_type, cache_params)
                    if cached_result:
                        data = json.loads(cached_result)
                        cache_hit = True
                        logger.info(
                            "study_cache_hit study_type=%s task_id=%s",
                            payload.study_type,
                            task_id,
                            extra={"trace_id": trace_id},
                        )
            except Exception as cache_err:
                logger.debug(
                    "Cache lookup failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id}
                )

        if cache_hit:
            # Use cached data
            pass
        elif payload.use_etap:
            if not payload.etap_project_path:
                raise ValueError("etap_project_path is required when use_etap=True")
            provider_name = "etap"
            # Offload the synchronous ETAP call to a thread so it doesn't
            # block the async event loop (ETAP COM calls can take 5-60 sec).
            from etap_integration.etap_provider import get_etap_provider

            provider_factory = get_etap_provider()
            provider = provider_factory()

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
            etap_study = mapping.get(payload.study_type)
            if etap_study is None:
                raise ValueError(f"No ETAP mapping for study type: {payload.study_type}")

            data = await asyncio.to_thread(
                provider.execute_study, payload.etap_project_path, etap_study
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

                    system_json = json.dumps(
                        payload.system.model_dump(), sort_keys=True, default=str
                    )
                    cache_params["system_hash"] = _hashlib.sha256(system_json.encode()).hexdigest()
                if study_cache:
                    await study_cache.set(
                        payload.study_type, cache_params, json.dumps(data, default=str)
                    )
            except Exception as cache_err:
                logger.debug(
                    "Cache store failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id}
                )

        _increment_counter("success")
        status = "success"
    except HTTPException:
        raise
    except ValueError as ve:
        # Validation errors (missing question, missing system, invalid params)
        # must return HTTP 400 Bad Request — not HTTP 200 with errors list.
        _increment_counter("failed")
        logger.warning(
            "study_run_validation_error study_type=%s error=%s",
            payload.study_type,
            str(ve),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(status_code=400, detail=str(ve)) from ve
    except Exception as e:
        _increment_counter("failed")
        logger.error(
            "study_run_failed study_type=%s error=%s",
            payload.study_type,
            str(e),
            extra={"trace_id": trace_id},
        )
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
