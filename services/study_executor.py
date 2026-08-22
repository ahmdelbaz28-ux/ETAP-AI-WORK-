"""
Study Executor — deep module for the study execution pipeline.

Owns the entire pipeline behind a single seam: validate → cache lookup →
build system → dispatch via STUDY_DISPATCH → AI failure-mode scan (F-12) →
risk scoring → serialize → cache store.

Created by the C3/C4 refactoring sprint to extract execution logic out of
the 886-line ``api/studies.py`` router file. The router is now a thin
adapter that delegates to :meth:`StudyExecutor.execute`.

Backward compatibility:
    ``api/studies.py`` re-exports ``_run_native_study`` and
    ``_build_system_from_spec`` as thin wrappers around this class so that
    the 12 test files and ``api/validation.py`` that import them directly
    continue to work without modification.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import time
from typing import Any, Dict, Optional

from api.feature_flags import FEATURE_FLAGS, is_feature_enabled
from api.pe_stamp import requires_stamp
from api.risk_scoring import compute_risk
from core.bootstrap import _add_execution_time, _increment_counter
from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.specs import StudyRequest, StudyResult, SystemSpec
from core_model.system import System
from core_model.transformer import Transformer
from engine.caching import StudyCache
from engine.dispatch import STUDY_DISPATCH, StudyRegistration

logger = logging.getLogger("engineering_service")

# Study types that require a System model to be provided.
_TYPES_REQUIRING_SYSTEM = {
    "load_flow",
    "short_circuit",
    "protection_coordination",
    "motor_starting",
    "harmonic_analysis",
}

# Canonical study-type aliases (REFERENCE.md §"Canonical Study Types").
_NATIVE_ALIASES = {
    "fault": "short_circuit",
    "coordination": "protection_coordination",
    "harmonic": "harmonic_analysis",
    "stability": "transient_stability",
    "opf": "optimal_power_flow",
}


class StudyExecutor:
    """Deep module: owns the entire study execution pipeline.

    Instantiation is cheap — all heavy imports (PowerSystemEngine, agent
    classes) are deferred to dispatch time via ``STUDY_DISPATCH`` entries.

    Parameters
    ----------
    cache
        Optional ``StudyCache`` instance for result caching. When ``None``,
        caching is silently skipped (used in tests and dry-run mode).
    """

    def __init__(self, cache: Optional[StudyCache] = None):
        self._cache = cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(self, payload: StudyRequest, trace_id: str = "unknown") -> StudyResult:
        """Execute a study request end-to-end.

        Returns a :class:`StudyResult` with ``success``, ``data``,
        ``warnings``, ``errors``, and timing/trace metadata.
        """
        task_id = payload.task_id or str(time.perf_counter())
        start = time.perf_counter()

        warnings: list[str] = []
        errors: list[str] = []
        data: dict[str, Any] = {}
        provider_name = "native"
        cache_hit = False

        self._validate_request(payload)

        if requires_stamp(payload.study_type) and not payload.pe_stamp:
            warnings.append(
                f"Study type '{payload.study_type}' requires a Professional Engineer (PE) stamp "
                "in most jurisdictions. Consider providing a PE stamp via the 'pe_stamp' field."
            )

        _increment_counter("request")
        logger.info(  # NOSONAR: user input is sanitized upstream
            "study_run_start study_type=%s use_etap=%s task_id=%s",
            payload.study_type,
            payload.use_etap,
            task_id,
            extra={"trace_id": trace_id},
        )

        try:
            if payload.use_etap:
                provider_name = "etap"
                data, warnings, errors = await self._run_etap_study(payload)
            else:
                cache = self._cache or self._init_cache()
                data, cache_hit = await self._lookup_cache(cache, payload, trace_id)

                if not cache_hit:
                    system = None
                    if payload.system:
                        try:
                            system = self._build_system_from_spec(payload.system)
                        except ValueError as ve:
                            raise ValueError(f"System spec error: {ve}") from ve

                    data = self._dispatch(
                        payload.study_type,
                        system,
                        payload.parameters,
                    )
                    provider_name = "native"
                    await self._store_cache_result(cache, payload, data, trace_id)

            _increment_counter("success")
            status = "success"
        except ValueError:
            raise
        except Exception as e:
            _increment_counter("failed")
            logger.exception(  # NOSONAR
                "study_run_failed study_type=%s error=%s",
                payload.study_type,
                str(e),
                extra={"trace_id": trace_id},
            )
            errors.append("Study execution failed")
            status = "failed"
            data = {}

        data = self._to_jsonable(data)

        if status == "success" and is_feature_enabled("AI_FAILURE_MODE_SCAN"):
            violations = self._scan_ai_failure_modes(data, payload.study_type)
            if violations:
                must_fix = [v for v in violations if v.get("severity") == "must_fix"]
                if must_fix:
                    errors.insert(
                        0,
                        f"AI failure mode scan blocked result: {len(must_fix)} MUST_FIX "
                        f"violations detected (F-12). See ai_failure_mode_violations in data.",
                    )
                    status = "failed"
                data["ai_failure_mode_violations"] = violations

        if status == "success":
            risk_info = compute_risk(payload.study_type, data)
            data["risk_score"] = risk_info["risk_score"]
            data["risk_violations"] = risk_info["risk_violations"]

        elapsed_sec = time.perf_counter() - start
        _add_execution_time(elapsed_sec)

        logger.info(  # NOSONAR
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

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_request(self, payload: StudyRequest) -> None:
        """Validate feature flag, system requirement, and pre-flight checks."""
        if not is_feature_enabled(payload.study_type):
            flag_info = FEATURE_FLAGS.get(payload.study_type, {})
            raise ValueError(
                f"This study type is currently disabled in production. "
                f"Status: {flag_info.get('status', 'unknown')}. "
                f"Description: {flag_info.get('description', 'No description')}"
            )

        if payload.study_type in _TYPES_REQUIRING_SYSTEM and payload.system is None:
            raise ValueError(
                "System configuration is required. Please provide a valid power system model."
            )

        if payload.system is not None:
            pf_result = self._pre_flight_check(payload.system.model_dump())
            if pf_result is not None:
                raise ValueError(pf_result["error"])

    # ------------------------------------------------------------------
    # System building (moved from api/studies.py)
    # ------------------------------------------------------------------

    def _build_system_from_spec(self, spec: SystemSpec) -> System:
        """Build a Python System object from a SystemSpec."""
        system = System(base_mva=spec.base_mva)
        bus_map: dict[int, Bus] = {}

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

    # ------------------------------------------------------------------
    # Dispatch (uses STUDY_DISPATCH table from engine/dispatch.py)
    # ------------------------------------------------------------------

    def _dispatch(self, study_type: str, system: Any, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a study using the unified STUDY_DISPATCH table.

        Delegates to ``PowerSystemEngine`` for native types, ``BaseAgent``
        subclasses for agent-routed types, and the Engineering Service HTTP
        API for external types.
        """
        canonical = _NATIVE_ALIASES.get(study_type, study_type)

        if canonical not in STUDY_DISPATCH:
            _supported = ", ".join(
                st for st, reg in STUDY_DISPATCH.items() if reg.handler_type == "native"
            )
            raise ValueError(
                f"Unsupported native study type: {canonical!r}. "
                f"Native engine supports: {_supported}."
            )

        registration = STUDY_DISPATCH[canonical]

        if registration.requires_system and system is None:
            raise ValueError(f"study_type '{canonical}' requires a 'system' to be provided")

        if registration.handler_type == "native":
            return self._dispatch_native(registration, system, parameters)
        if registration.handler_type == "agent":
            return self._dispatch_agent(canonical, parameters)
        raise ValueError(
            f"Unsupported handler_type '{registration.handler_type}' for study '{canonical}'"
        )

    def _dispatch_native(
        self, registration: StudyRegistration, system: Any, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a native study via PowerSystemEngine."""
        from engine.engine import PowerSystemEngine

        engine = PowerSystemEngine(system)
        method = getattr(engine, registration.handler)
        missing = [p for p in registration.required_params if parameters.get(p) is None]

        if registration.handler == "run_load_flow":
            return method()
        if registration.handler == "run_fault_analysis":
            if not missing or "bus_id" in parameters:
                fault_type = parameters.get("fault_type", "three_phase")
                bus_id = parameters.get("bus_id")
                if bus_id is None and system and hasattr(system, "buses") and system.buses:
                    bus_id = system.buses[0].bus_id
                if bus_id is None:
                    raise ValueError("bus_id is required for fault analysis")
                return method(fault_type, bus_id)
            raise ValueError("bus_id must be provided for fault study")
        if registration.handler == "run_arc_flash":
            return method(
                voltage_kv=float(parameters.get("voltage_kv", 13.8)),
                bolted_fault_current_ka=float(parameters.get("bolted_fault_current_ka", 20.0)),
                arc_duration_sec=float(parameters.get("arc_duration_sec", 0.1)),
                working_distance_mm=float(parameters.get("working_distance_mm", 610.0)),
                electrode_config=str(parameters.get("electrode_config", "VCB")),
                enclosure_type=str(parameters.get("enclosure_type", "box")),
                enclosure_width_mm=float(parameters.get("enclosure_width_mm", 508.0)),
                enclosure_height_mm=float(parameters.get("enclosure_height_mm", 508.0)),
                enclosure_depth_mm=float(parameters.get("enclosure_depth_mm", 508.0)),
            )
        if registration.handler == "run_protection_coordination":
            upstream = parameters.get("upstream_relay_id", 1)
            downstream = parameters.get("downstream_relay_id", 2)
            fault_currents = parameters.get("fault_currents", [2.0, 5.0, 10.0, 20.0])
            return method(upstream, downstream, fault_currents)
        # Generic fallback for any future native handler
        return method(**parameters)

    def _dispatch_agent(self, study_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an agent-routed study via BaseAgent subclass."""
        if study_type == "etap_expert":
            from agents.etap_expert_agent import ETAPExpertAgent

            agent = ETAPExpertAgent()
            question = str(parameters.get("question", "")).strip()
            if not question:
                raise ValueError("'question' field is required for study_type='etap_expert'")
            return agent.answer(question)

        if study_type == "etap_gui":
            from agents.etap_gui_agent import ETAPGUIAgent

            agent = ETAPGUIAgent()
            question = str(parameters.get("question", "")).strip()
            if not question:
                raise ValueError("'question' field is required for study_type='etap_gui'")
            return agent.answer(question)

        if study_type == "ahmed_etap_orchestration" or study_type == "ahmed_etap":
            from agents.ahmed_etap_orchestrator import AhmedETAPSkillAgent
            from agents.models import EngineeringTask, StudyType, get_orchestrator

            agent = AhmedETAPSkillAgent(orchestrator=get_orchestrator())
            inner_study = str(parameters.get("study_type", "load_flow"))
            try:
                st_enum = StudyType(inner_study)
            except ValueError:
                st_enum = StudyType.LOAD_FLOW
            skill_task = EngineeringTask(
                task_id=f"ahmed_etap_skill_{int(time.time())}",
                description=f"Skill-orchestrated {inner_study}",
                study_types=[st_enum],
                parameters=parameters,
            )
            try:
                asyncio.get_running_loop()
                import concurrent.futures as _cf

                with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                    result = pool.submit(lambda: asyncio.run(agent.execute(skill_task))).result()
            except RuntimeError:
                result = asyncio.run(agent.execute(skill_task))
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

        raise ValueError(f"Unsupported agent-routed study type: {study_type}")

    # ------------------------------------------------------------------
    # ETAP provider
    # ------------------------------------------------------------------

    async def _run_etap_study(self, payload: StudyRequest) -> tuple[dict, list, list]:
        """Execute an ETAP study. Returns (data, warnings, errors)."""
        if not payload.etap_project_path:
            raise ValueError("etap_project_path is required when use_etap=True")

        from etap_integration.etap_provider import ETAPStudyType, get_etap_provider

        provider = get_etap_provider()

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
            provider.execute_study,
            payload.etap_project_path,
            etap_study,
        )
        warnings = data.pop("warnings", [])
        errors = data.pop("errors", [])
        if not data.pop("success", True):
            errors.append("ETAP study reported failure")
        return data, warnings, errors

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _init_cache(self) -> Optional[StudyCache]:
        try:
            _cache_disabled = os.getenv("ENGINEERING_SERVICE_CACHE_DISABLED", "").lower() == "true"
            _redis_url = (
                "memory://fallback"
                if _cache_disabled
                else os.getenv("REDIS_URL", "redis://localhost:6379")
            )
            return StudyCache(redis_url=_redis_url, ttl=3600)
        except Exception:
            logger.debug("StudyCache init failed (non-fatal)")
            return None

    def _build_cache_params(self, payload: StudyRequest) -> dict:
        cache_params = {"study_type": payload.study_type, "parameters": payload.parameters}
        if payload.system:
            system_json = json.dumps(
                payload.system.model_dump(),
                sort_keys=True,
                default=str,
            )
            cache_params["system_hash"] = hashlib.sha256(system_json.encode()).hexdigest()
        return cache_params

    async def _lookup_cache(
        self, study_cache: Optional[StudyCache], payload: StudyRequest, trace_id: str
    ) -> tuple[dict, bool]:
        if not study_cache or payload.use_etap:
            return {}, False
        try:
            cache_params = self._build_cache_params(payload)
            cached_result = await study_cache.get(payload.study_type, cache_params)
            if cached_result:
                logger.info(
                    "study_cache_hit study_type=%s task_id=%s",
                    payload.study_type,
                    trace_id,
                    extra={"trace_id": trace_id},
                )
                return json.loads(cached_result), True
        except Exception:
            pass
        return {}, False

    async def _store_cache_result(
        self, study_cache: Optional[StudyCache], payload: StudyRequest, data: dict, trace_id: str
    ) -> None:
        if not study_cache:
            return
        try:
            cache_params = self._build_cache_params(payload)
            await study_cache.set(payload.study_type, cache_params, data)
        except Exception as cache_err:
            logger.debug(
                "Cache store failed (non-fatal): %s",
                cache_err,
                extra={"trace_id": trace_id},
            )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _to_jsonable(self, obj: Any) -> Any:
        """Recursively convert numpy types and other non-JSON-native values."""
        import numpy as np

        if obj is None or isinstance(obj, (str, bool)):
            return obj
        if isinstance(obj, (int, float)):
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            return obj
        if isinstance(obj, complex):
            return {"re": self._to_jsonable(obj.real), "im": self._to_jsonable(obj.imag)}
        if isinstance(obj, np.ndarray):
            return [self._to_jsonable(x) for x in obj.tolist()]
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
            return {"real": self._to_jsonable(obj.real), "imag": self._to_jsonable(obj.imag)}
        if isinstance(obj, dict):
            return {str(k): self._to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return [self._to_jsonable(x) for x in obj]
        try:
            return json.loads(json.dumps(obj, default=str))
        except Exception:
            return str(obj)

    # ------------------------------------------------------------------
    # Pre-flight checks
    # ------------------------------------------------------------------

    def _pre_flight_basic(self, system: dict) -> Optional[dict]:
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

    def _pre_flight_lines(self, lines: list, bus_ids: set) -> Optional[dict]:
        for line in lines:
            if line.get("r1", 0) <= 0 and line.get("x1", 0) <= 0:
                return {"error": f"Line {line.get('line_id')} has zero/negative impedance"}
            if line.get("from_bus_id") not in bus_ids:
                return {
                    "error": f"Line {line.get('line_id')} references unknown from_bus {line.get('from_bus_id')}"
                }
            if line.get("to_bus_id") not in bus_ids:
                return {
                    "error": f"Line {line.get('line_id')} references unknown to_bus {line.get('to_bus_id')}"
                }
        return None

    def _pre_flight_isolated_buses(self, bus_ids: set, lines: list) -> Optional[dict]:
        connected_buses = set()
        for line in lines:
            connected_buses.add(line.get("from_bus_id"))
            connected_buses.add(line.get("to_bus_id"))
        isolated = bus_ids - connected_buses
        if isolated and len(bus_ids) > 1:
            return {"error": f"Isolated buses with no connections: {isolated}"}
        return None

    def _pre_flight_voltage_bounds(self, buses: list) -> Optional[dict]:
        for bus in buses:
            v = bus.get("voltage_magnitude")
            if v is not None and (v < 0.01 or v > 1.5):
                return {
                    "error": f"Bus {bus.get('bus_id')} voltage {v} pu out of realistic range (0.01-1.5)"
                }
        return None

    def _pre_flight_check(self, system: dict) -> Optional[dict]:
        """Validate system configuration before running a study."""
        result = self._pre_flight_basic(system)
        if result is not None:
            return result
        buses = system.get("buses", [])
        lines = system.get("lines", [])
        bus_ids = {b.get("bus_id") for b in buses if b.get("bus_id") is not None}
        result = self._pre_flight_lines(lines, bus_ids)
        if result is not None:
            return result
        result = self._pre_flight_isolated_buses(bus_ids, lines)
        if result is not None:
            return result
        return self._pre_flight_voltage_bounds(buses)

    # ------------------------------------------------------------------
    # AI failure mode scan (F-12)
    # ------------------------------------------------------------------

    def _scan_ai_failure_modes(self, data: dict[str, Any], study_type: str) -> list[dict[str, str]]:
        """Scan study result data for AI failure mode patterns (F-12)."""
        try:
            from guards.ai_failure_modes import AIFailureModeDetector  # noqa: F401
        except ImportError:
            return []

        try:
            data_str = json.dumps(data, default=str, indent=2)
        except Exception:
            data_str = str(data)

        if len(data_str) < 50:
            return []

        try:
            detector = AIFailureModeDetector()
            result = detector.scan(data_str, language="python")
            violations = []
            for v in result.violations:
                violations.append(
                    {
                        "rule_id": v.rule_id,
                        "severity": v.severity.value,
                        "description": v.description[:200],
                    }
                )
            if violations:
                must_fix_count = sum(1 for v in violations if v["severity"] == "must_fix")
                if must_fix_count:
                    logger.error(
                        "F-12: AI failure mode scan found %d MUST_FIX violations in %s result",
                        must_fix_count,
                        study_type,
                    )
                else:
                    logger.info(
                        "F-12: AI failure mode scan found %d SHOULD_FIX violations in %s result",
                        len(violations),
                        study_type,
                    )
            return violations
        except Exception as scan_err:
            logger.warning("F-12: AI failure mode scan failed (non-blocking): %s", scan_err)
            return []
