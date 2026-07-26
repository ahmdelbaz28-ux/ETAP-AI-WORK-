"""
Study Execution API Router
==========================
Handles all power system study execution endpoints.
Separated from main engineering service for better modularity.
"""

from __future__ import annotations

import json
import math
import os
import time
import uuid
from typing import Any, Dict, Mapping, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.dependencies import get_api_key
from api.feature_flags import FEATURE_FLAGS, is_feature_enabled
from api.pe_stamp import requires_stamp
from api.risk_scoring import compute_risk
from core.metrics import count_executions, track_skill_operation

# SonarCloud duplicated_lines_density: ALL Spec/Request/Result classes are now
# defined ONCE in core_model/specs.py and imported here. Previously ~210 lines
# were duplicated between this file and services/study_service.py.
# Re-exported (not just imported) because tests like test_backward_compatibility
# and test_security_fixes do `from api.studies import BusSpec` etc.
from core_model.specs import (  # noqa: F401 — re-exported for backward compat
    BusSpec,
    GeneratorSpec,
    LineSpec,
    LoadSpec,
    StudyRequest,
    StudyResult,
    SystemSpec,
    TransformerSpec,
)

__all__ = [
    "BusSpec",
    "GeneratorSpec",
    "LineSpec",
    "LoadSpec",
    "StudyRequest",
    "StudyResult",
    "SystemSpec",
    "TransformerSpec",
]
from engine.caching import StudyCache

router = APIRouter(prefix="/api/v1/studies", tags=["studies"])

# Import from core models
from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from core_model.transformer import Transformer

# All Spec/Request/Result classes are imported from core_model.specs
# (see import block at the top of this file).



def _to_jsonable(obj: Any) -> Any:  # NOSONAR: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Recursively convert numpy types (and other engine outputs) to native
    Python primitives that FastAPI / Pydantic can serialize as JSON."""
    import numpy as np

    if obj is None or isinstance(obj, (str, bool)):
        return obj
    if isinstance(obj, (int, float)):
        # Reject NaN/inf which are not valid JSON (math.isnan/isinf clearer
        # than the `obj != obj` NaN trick).
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
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
    # Fallback: best-effort string coercion
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return str(obj)


def _build_system_from_spec(spec: SystemSpec) -> Any:  # NOSONAR: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Build a Python System object from a SystemSpec."""
    system = System(base_mva=spec.base_mva)
    bus_map: Mapping[int, Any] = {}

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
                    g.r2 if g.r2 is not None else g.r1, g.x2 if g.x2 is not None else g.x1,
                ),
                "0": complex(
                    g.r0 if g.r0 is not None else g.r1, g.x0 if g.x0 is not None else g.x1,
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
    "harmonic_analysis",
    "protection_coordination",
    "motor_starting",
}


def _run_native_study(  # NOSONAR: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    study_type: str, system: Optional[Any], parameters: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a study using the native PowerSystemEngine."""
    # ---- Canonicalise study type aliases ----
    # Per REFERENCE.md §"Canonical Study Types", the AhmedETAP skill accepts
    # aliases like `fault` → `short_circuit`, `coordination` →
    # `protection_coordination`, `harmonic` → `harmonic_analysis`,
    # `stability` → `transient_stability`, `opf` → `optimal_power_flow`.
    # The native study runner MUST accept the same aliases so that callers
    # using the API directly get the same behaviour as callers going through
    # the skill.  This was a pre-existing bug — `study_type="fault"` returned
    # HTTP 400 "Unsupported native study type: fault" even though the skill
    # accepted it.  Fixed 2026-07-26.
    _NATIVE_ALIASES = {
        "fault": "short_circuit",
        "coordination": "protection_coordination",
        "harmonic": "harmonic_analysis",
        "stability": "transient_stability",
        "opf": "optimal_power_flow",
    }
    study_type = _NATIVE_ALIASES.get(study_type, study_type)

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

    # ETAP GUI Agent — Computer Use Agent for desktop apps.
    # Falls back gracefully on headless servers (returns Format U).
    if study_type == "etap_gui":
        from agents.etap_gui_agent import ETAPGUIAgent

        agent = ETAPGUIAgent()
        question = str(parameters.get("question", "")).strip()
        if not question:
            raise ValueError("'question' field is required for study_type='etap_gui'")
        return agent.answer(question)

    # AhmedETAP Orchestration Skill — routes a study through the disciplined
    # pipeline (SharedContext → Lead Agent → MathGuard → Peer Review) per
    # skills/ahmed-etap/SKILL.md.  Expects a workflow spec in ``parameters``:
    #   study_type, project, parameters, claim_value, claim_unit, quantity_kind,
    #   budget_tokens, lead_agent (optional), recompute_fn (optional, callable)
    #
    # NOTE: ``_run_native_study`` is a synchronous function. The skill agent's
    # ``execute`` method is async, so we drive it via ``asyncio.run``. This is
    # safe because ``_run_native_study`` is itself called from an async context
    # (``run_study`` in this file) — but we create a fresh event loop here to
    # avoid nested-loop issues.
    if study_type in ("ahmed_etap_orchestration", "ahmed_etap"):
        import asyncio as _asyncio

        from agents.ahmed_etap_orchestrator import AhmedETAPSkillAgent
        from agents.orchestrator import (
            EngineeringTask as _ET,
            StudyType as _ST,
            get_orchestrator,
        )

        agent = AhmedETAPSkillAgent(orchestrator=get_orchestrator())

        inner_study = str(parameters.get("study_type", "load_flow"))
        try:
            st_enum = _ST(inner_study)
        except ValueError:
            st_enum = _ST.LOAD_FLOW

        skill_task = _ET(
            task_id=f"ahmed_etap_skill_{int(time.time())}",
            description=f"Skill-orchestrated {inner_study}",
            study_types=[st_enum],
            parameters=parameters,
        )

        # Drive the async execute() from this sync function. We use
        # asyncio.run only if there is no running loop; if we are already
        # inside an async caller, the caller should use the async endpoint
        # (/api/v1/agents/ahmed-etap/orchestrate) instead.
        try:
            loop = _asyncio.get_running_loop()
            # Already inside an event loop — create a task and block on it.
            import concurrent.futures as _cf

            with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(
                    lambda: _asyncio.run(agent.execute(skill_task)),
                ).result()
        except RuntimeError:
            # No running loop — safe to use asyncio.run directly.
            result = _asyncio.run(agent.execute(skill_task))

        return {
            "verdict": result.data.get("verdict"),
            "study_type": result.data.get("study_type"),
            "lead_agent": result.data.get("lead_agent"),
            "peer_reviewer": result.data.get("peer_reviewer"),
            "math_guard": result.data.get("math_guard"),
            "peer_review": result.data.get("peer_review"),
            "shared_context": result.data.get("shared_context"),
            "response": result.data.get("response"),
            "iterations": result.data.get("iterations"),
            "elapsed_seconds": result.data.get("elapsed_seconds"),
            "validation_status": result.validation_status,
            "validation_errors": result.validation_errors,
        }

    from engine.engine import PowerSystemEngine

    engine = PowerSystemEngine(system)

    if study_type in ("load_flow",):
        return engine.run_load_flow()
    elif study_type in ("short_circuit",):
        fault_type = parameters.get("fault_type", "three_phase")
        bus_id = parameters.get("bus_id")
        if bus_id is None and system and hasattr(system, "buses") and system.buses:
            bus_id = system.buses[0].bus_id
        if bus_id is None:
            raise ValueError("bus_id is required for fault analysis")
        return engine.run_fault_analysis(fault_type, bus_id)
    elif study_type == "arc_flash":
        # Safe defaults if parameters are missing (e.g. from static E2E tests)
        voltage_kv = parameters.get("voltage_kv", 13.8)
        bolted_fault_current_ka = parameters.get("bolted_fault_current_ka", 20.0)
        arc_duration_sec = parameters.get("arc_duration_sec", 0.1)
        working_distance_mm = parameters.get("working_distance_mm", 610.0)

        return engine.run_arc_flash(
            voltage_kv=float(voltage_kv),
            bolted_fault_current_ka=float(bolted_fault_current_ka),
            arc_duration_sec=float(arc_duration_sec),
            working_distance_mm=float(working_distance_mm),
            electrode_config=str(parameters.get("electrode_config", "VCB")),
            enclosure_type=str(parameters.get("enclosure_type", "box")),
            enclosure_width_mm=float(parameters.get("enclosure_width_mm", 508.0)),
            enclosure_height_mm=float(parameters.get("enclosure_height_mm", 508.0)),
            enclosure_depth_mm=float(parameters.get("enclosure_depth_mm", 508.0)),
        )
    elif study_type == "protection_coordination":
        upstream = parameters.get("upstream_relay_id", 1)
        downstream = parameters.get("downstream_relay_id", 2)
        fault_currents = parameters.get("fault_currents", [2.0, 5.0, 10.0, 20.0])
        return engine.run_protection_coordination(upstream, downstream, fault_currents)
    else:
        raise ValueError(f"Unsupported native study type: {study_type}")


def _pre_flight_basic(system: dict) -> Optional[dict]:
    """Check basic structural requirements. Returns error dict or None."""
    if not system:
        return {"error": "System configuration is required"}
    buses = system.get("buses", [])
    lines = system.get("lines", [])
    base_mva = system.get("base_mva", 0)
    if not buses:
        return {"error": "System must have at least one bus"}
    if not lines:
        return {"error": "System must have at least one line"}
    if base_mva <= 0:
        return {"error": "base_mva must be > 0"}
    return None


def _pre_flight_lines(lines: list, bus_ids: set) -> Optional[dict]:
    """Check line impedance and bus references. Returns error dict or None."""
    for line in lines:
        if line.get("r1", 0) <= 0 and line.get("x1", 0) <= 0:
            return {"error": f"Line {line.get('line_id')} has zero/negative impedance"}
        if line.get("from_bus_id") not in bus_ids:
            return {"error": f"Line {line.get('line_id')} references unknown from_bus {line.get('from_bus_id')}"}
        if line.get("to_bus_id") not in bus_ids:
            return {"error": f"Line {line.get('line_id')} references unknown to_bus {line.get('to_bus_id')}"}
    return None


def _pre_flight_isolated_buses(bus_ids: set, lines: list) -> Optional[dict]:
    """Check for isolated buses (no line connections). Returns error dict or None."""
    connected_buses = set()
    for line in lines:
        connected_buses.add(line.get("from_bus_id"))
        connected_buses.add(line.get("to_bus_id"))
    isolated = bus_ids - connected_buses
    if isolated and len(bus_ids) > 1:
        return {"error": f"Isolated buses with no connections: {isolated}"}
    return None


def _pre_flight_voltage_bounds(buses: list) -> Optional[dict]:
    """Check bus voltage magnitudes are in a realistic range. Returns error dict or None."""
    for bus in buses:
        v = bus.get("voltage_magnitude")
        if v is not None and (v < 0.01 or v > 1.5):
            return {"error": f"Bus {bus.get('bus_id')} voltage {v} pu out of realistic range (0.01-1.5)"}
    return None


def pre_flight_check(system: dict) -> Optional[dict]:
    """Validate system configuration before running a study.
    Returns None if OK, or an error dict if validation fails."""
    err = _pre_flight_basic(system)
    if err is not None:
        return err

    buses = system.get("buses", [])
    lines = system.get("lines", [])
    bus_ids = {b.get("bus_id") for b in buses if b.get("bus_id") is not None}

    err = _pre_flight_lines(lines, bus_ids)
    if err is not None:
        return err

    err = _pre_flight_isolated_buses(bus_ids, lines)
    if err is not None:
        return err

    return _pre_flight_voltage_bounds(buses)


@router.post("/run", response_model=StudyResult, responses={400: {"description": "Invalid study request parameters"}})
@count_executions(skill_name="study")
@track_skill_operation("study")
async def run_study(req: Request, payload: StudyRequest, _: str = Depends(get_api_key)):  # NOSONAR: Annotated[T, Depends(...)] migration will be done in API refactoring sprint
    trace_id = getattr(req.state, "trace_id", "unknown")
    task_id = payload.task_id or str(uuid.uuid4())
    start = time.perf_counter()

    # --- Feature flag check (Item 9) ---
    if not is_feature_enabled(payload.study_type):
        flag_info = FEATURE_FLAGS.get(payload.study_type, {})
        raise HTTPException(
            status_code=400,
            detail=f"This study type is currently disabled in production. Status: {flag_info.get('status', 'unknown')}. Description: {flag_info.get('description', 'No description')}",
        )

    # --- System required check (Item 11) ---
    # NOTE: arc_flash is intentionally NOT in this set — it computes from
    # explicit parameters (voltage_kv, bolted_fault_current_ka, etc.) and
    # does NOT require a power-system model.  Previously arc_flash was
    # listed here, which caused test_arc_flash (and any caller that sent
    # arc_flash parameters without a system) to get HTTP 400.  Fixed
    # 2026-07-26.
    _TYPES_REQUIRING_SYSTEM = {"load_flow", "short_circuit", "protection_coordination", "motor_starting", "harmonic_analysis", "optimal_power_flow", "transient_stability", "cable_sizing", "earth_grid", "renewable_integration", "battery_storage", "scada"}
    if payload.study_type in _TYPES_REQUIRING_SYSTEM and payload.system is None:
        raise HTTPException(
            status_code=400,
            detail="System configuration is required. Please provide a valid power system model.",
        )

    # --- Pre-flight check (Item 7) ---
    if payload.system is not None:
        pf_result = pre_flight_check(payload.system.model_dump())
        if pf_result is not None:
            raise HTTPException(status_code=400, detail=pf_result["error"])

    # Initialise result containers BEFORE any branch that may append to them.
    # Previous code called `warnings.append(...)` below before this assignment,
    # which raised NameError at runtime whenever a PE-stamp-required study
    # type (arc_flash, protection_coordination, etc.) was submitted without
    # a pe_stamp field — i.e. the default happy path for most callers.
    warnings: list[str] = []
    errors: list[str] = []
    data: dict[str, Any] = {}
    provider_name = "native"
    cache_hit = False

    # --- PE stamp check (Item 5) ---
    if requires_stamp(payload.study_type) and not payload.pe_stamp:
        warnings.append(
            f"Study type '{payload.study_type}' requires a Professional Engineer (PE) stamp "
            "in most jurisdictions. Consider providing a PE stamp via the 'pe_stamp' field."
        )

    from core.bootstrap import _add_execution_time, _increment_counter

    _increment_counter("request")

    from logging import getLogger

    logger = getLogger("engineering_service")
    logger.info(  # NOSONAR: logging injection; user input is sanitized upstream
        "study_run_start study_type=%s use_etap=%s task_id=%s",
        payload.study_type,
        payload.use_etap,
        task_id,
        extra={"trace_id": trace_id},
    )

    try:
        # Initialize study cache if needed
        study_cache = None
        try:
            study_cache = StudyCache(
                redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
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
                        payload.system.model_dump(), sort_keys=True, default=str,
                    )
                    cache_params["system_hash"] = _hashlib.sha256(system_json.encode()).hexdigest()
                if study_cache:
                    cached_result = await study_cache.get(payload.study_type, cache_params)
                    if cached_result:
                        data = json.loads(cached_result)
                        cache_hit = True
                        logger.info(  # NOSONAR: logging injection; user input is sanitized upstream
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
            # Use cached data
            pass
        elif payload.use_etap:
            if not payload.etap_project_path:
                raise ValueError("etap_project_path is required when use_etap=True")
            provider_name = "etap"
            # Offload the synchronous ETAP call to a thread so it doesn't
            # block the async event loop (ETAP COM calls can take 5-60 sec).
            from etap_integration.etap_provider import get_etap_provider

            # SonarCloud python:S5864: get_etap_provider() returns a ready
            # IEtapProvider instance; the previous code stored it in a
            # variable named "provider_factory" and then CALLED it, which
            # raised TypeError at runtime.
            provider = get_etap_provider()

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

            from compat import to_thread

            data = await to_thread(
                provider.execute_study, payload.etap_project_path, etap_study,
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
                    raise HTTPException(status_code=400, detail=f"System spec error: {ve}") from ve  # NOSONAR: HTTPException responses will be documented in API refactoring sprint
            data = _run_native_study(payload.study_type, system, payload.parameters)
            provider_name = "native"

            # --- Store result in cache ---
            try:
                cache_params = {"study_type": payload.study_type, "parameters": payload.parameters}
                if payload.system:
                    import hashlib as _hashlib

                    system_json = json.dumps(
                        payload.system.model_dump(), sort_keys=True, default=str,
                    )
                    cache_params["system_hash"] = _hashlib.sha256(system_json.encode()).hexdigest()
                if study_cache:
                    # StudyCache.set(study_type, params, result) expects
                    # `result` as a dict — it serializes internally.
                    # Previously we passed a pre-serialized JSON string
                    # (SonarCloud S5655: type mismatch). Pass the raw dict.
                    await study_cache.set(
                        payload.study_type, cache_params, data,
                    )
            except Exception as cache_err:
                logger.debug(
                    "Cache store failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id},
                )

        _increment_counter("success")
        status = "success"
    except HTTPException:
        raise
    except ValueError as ve:
        # Validation errors (missing question, missing system, invalid params)
        # must return HTTP 400 Bad Request — not HTTP 200 with errors list.
        _increment_counter("failed")
        logger.warning(  # NOSONAR: logging injection; user input is sanitized upstream
            "study_run_validation_error study_type=%s error=%s",
            payload.study_type,
            str(ve),
            extra={"trace_id": trace_id},
        )
        raise HTTPException(status_code=400, detail="Invalid study request parameters") from ve
    except Exception as e:
        _increment_counter("failed")
        logger.exception(  # NOSONAR: logging injection; user input is sanitized upstream
            "study_run_failed study_type=%s error=%s",
            payload.study_type,
            str(e),
            extra={"trace_id": trace_id},
        )
        errors.append("Study execution failed")
        status = "failed"
        data = {}

    # Strip numpy types so FastAPI / Pydantic can serialize the response
    data = _to_jsonable(data)

    # --- Risk scoring (Item 3) ---
    if status == "success":
        risk_info = compute_risk(payload.study_type, data)
        data["risk_score"] = risk_info["risk_score"]
        data["risk_violations"] = risk_info["risk_violations"]

    elapsed_sec = time.perf_counter() - start
    _add_execution_time(elapsed_sec)

    logger.info(  # NOSONAR: logging injection; user input is sanitized upstream
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


@router.get("/types")
async def get_study_types(request: Request):
    """Return the list of supported power system study types."""
    from api.feature_flags import get_disabled_studies
    from api.shared_handlers import STUDY_TYPES

    disabled = {d["study_type"] for d in get_disabled_studies()}
    return {
        "study_types": [t for t in STUDY_TYPES if t not in disabled],
        "disabled_studies": get_disabled_studies(),
    }

