"""
Study Executor — native engineering executor behind Canonical Execution Orchestrator (Phase 7).

Owns the native engineering execution pipeline behind the canonical contract:
validate spec -> build system -> dispatch via STUDY_DISPATCH ->
AI failure-mode scan (F-12) -> engineering assertions -> risk scoring -> serialize.

Architecture:
    API
     ↓
    ExecutionRequest
     ↓
    Canonical Execution Orchestrator
     ↓
    StudyExecutor (native executor)

Governance responsibilities (tenant isolation, identity, maker-checker approval,
idempotency, and audit event persistence) are managed by ExecutionOrchestrator.
StudyExecutor retains all reusable mathematical and physical calculation logic.

Backward compatibility:
    api/studies.py re-exports _run_native_study, _build_system_from_spec,
    _to_jsonable, and pre_flight_check as thin wrappers around this class.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import time
import uuid
from typing import Any, Dict, Optional

from api.feature_flags import FEATURE_FLAGS, is_feature_enabled
from api.risk_scoring import compute_risk
from core.exceptions import SpecializedExecutionUnavailableError
from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.specs import StudyRequest, StudyResult, SystemSpec
from core_model.system import System
from core_model.transformer import Transformer
from engine.caching import StudyCache
from engine.dispatch import STUDY_DISPATCH, StudyRegistration
from services.execution_request import ExecutionRequest

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

from etap_integration.etap_provider import ETAPStudyType

# Supported ETAP study types and their mapping to ETAPStudyType enum (canonical source of truth).
_ETAP_STUDY_TYPE_MAP: dict[str, ETAPStudyType] = {
    "etap_load_flow": ETAPStudyType.LOAD_FLOW,
    "etap_short_circuit": ETAPStudyType.SHORT_CIRCUIT,
    "etap_arc_flash": ETAPStudyType.ARC_FLASH,
    "etap_harmonic_analysis": ETAPStudyType.HARMONIC_ANALYSIS,
    "etap_optimal_power_flow": ETAPStudyType.OPTIMAL_POWER_FLOW,
    "etap_motor_starting": ETAPStudyType.MOTOR_STARTING,
    "etap_protection_coordination": ETAPStudyType.PROTECTION_COORDINATION,
}
_ETAP_STUDY_TYPES: frozenset[str] = frozenset(_ETAP_STUDY_TYPE_MAP.keys())


class StudyExecutor:
    """Native engineering executor behind Canonical Execution Orchestrator (Phase 7).

    Executes native power-system numerical calculations (load_flow, short_circuit,
    arc_flash, protection_coordination) and manages reusable engineering logic.

    Parameters
    ----------
    cache
        Optional ``StudyCache`` instance for result caching.
    """

    def __init__(self, cache: Optional[StudyCache] = None):
        self._cache = cache

    # ------------------------------------------------------------------
    # Canonical Native Execution Interface (Phase 7)
    # ------------------------------------------------------------------

    def execute_native(self, request: ExecutionRequest) -> StudyResult:
        """Native engineering executor method invoked by ExecutionOrchestrator when executor_kind == 'native'.

        Owns the native execution pipeline:
        build system model -> pre-flight physics checks -> PowerSystemEngine dispatch ->
        serialize -> engineering assertions -> risk scoring.

        Governance responsibilities (tenant isolation, authentication, maker-checker,
        idempotency, and audit logging) are owned by ExecutionOrchestrator.
        """
        system_input = request.get_system()
        params = request.get_parameters()
        trace_id = request.trace_id
        task_id = request.request_id

        # 1. Build system model from spec if provided
        built_system = None
        if system_input is not None:
            try:
                built_system = self._build_system_from_spec(system_input)
            except ValueError as ve:
                raise ValueError(f"System spec error: {ve}") from ve

            # Pre-flight physics check
            if hasattr(system_input, "model_dump"):
                pf = self._pre_flight_check(system_input.model_dump())
            elif isinstance(system_input, dict):
                pf = self._pre_flight_check(system_input)
            else:
                pf = None
            if pf is not None:
                raise ValueError(pf["error"])

        canonical = _NATIVE_ALIASES.get(request.capability_id, request.capability_id)
        start_wall = time.time()
        start = time.perf_counter()
        errors: list[str] = []
        warnings: list[str] = []

        # Phase 14: Cache Identity and Input Hashes
        cache_params = self._build_cache_params(
            request,
            provider="native",
            executor_kind="native",
            solver="newton_raphson" if canonical == "load_flow" else canonical,
            engine_version="2.1.0",
        )

        try:
            data = self._dispatch(
                canonical,
                built_system,
                params,
            )
            data = self._to_jsonable(data)
            status = "success"
        except ValueError:
            raise
        except Exception as e:
            logger.exception(  # NOSONAR
                "native_study_failed study_type=%s error=%s",
                canonical,
                str(e),
                extra={"trace_id": trace_id},
            )
            errors.append("Study execution failed")
            status = "failed"
            data = {}

        # Step 2: Executor Validation
        if status == "success" and isinstance(data, dict):
            if canonical in ("load_flow", "optimal_power_flow") and data.get("converged") is False:
                status = "failed"
                errors.append("Load flow solver did not converge")

        # Step 3: Canonical Engineering Validation (Phase 13 Authority)
        validation_status = True
        validation_report: dict[str, Any] = {}
        if status == "success":
            status = self._apply_post_execution_checks(data, canonical, errors)
            validation_status = data.get("validation_status", status == "success")
            validation_report = data.get("validation_report", {})
            if "engineering_assertion_warnings" in data:
                for w in data["engineering_assertion_warnings"]:
                    msg = w.get("message") if isinstance(w, dict) else str(w)
                    if msg and msg not in warnings:
                        warnings.append(msg)
        else:
            validation_status = False

        # Step 4: Risk Assessment
        risk_info = compute_risk(canonical, data) if data else {"risk_score": "low"}
        raw_risk_score = data.get("risk_score") or risk_info.get("risk_score", "low")
        risk_class = raw_risk_score if isinstance(raw_risk_score, str) else "low"
        risk_score_numeric = {
            "low": 0.1,
            "medium": 0.4,
            "high": 0.7,
            "critical": 1.0,
        }.get(risk_class, 0.0)

        # Step 5: Canonical Result (Phase 12)
        completed_wall = time.time()
        elapsed_sec = time.perf_counter() - start
        exec_status = "completed" if status == "success" else "failed"

        execution_id = request.execution_id or task_id or uuid.uuid4().hex
        provenance = {
            "execution_id": execution_id,
            "request_id": request.request_id,
            "tenant_id": request.tenant_id,
            "provider": "native",
            "executor_kind": "native",
            "solver": "newton_raphson" if canonical == "load_flow" else canonical,
            "engine_version": "2.1.0",
            "trace_id": trace_id,
            "task_id": task_id,
            "timestamp": completed_wall,
            "validated_by": "EngineeringAssertionLayer",
        }

        return StudyResult(
            execution_id=execution_id,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            capability_id=request.capability_id,
            capability_version=request.capability_version or "1.0.0",
            status=exec_status,
            success=status == "success",
            provider="native",
            executor_kind="native",
            solver="newton_raphson" if canonical == "load_flow" else canonical,
            engine_version="2.1.0",
            input_snapshot_hash=cache_params.get("input_hash", ""),
            system_snapshot_hash=cache_params.get("system_snapshot_hash", ""),
            parameter_hash=cache_params.get("parameters_hash", ""),
            result=data,
            data=data,
            results=data,
            validation_status=validation_status,
            validation_report=validation_report,
            risk_class=risk_class,
            risk_score=risk_score_numeric,
            warnings=warnings,
            errors=errors,
            provenance=provenance,
            trace_id=trace_id,
            task_id=task_id,
            result_id=None,
            created_at=start_wall,
            completed_at=completed_wall,
            execution_time_sec=round(elapsed_sec, 3),
            study_type=request.capability_id,
        )

    # ------------------------------------------------------------------
    # External / Legacy Adapter Interface
    # ------------------------------------------------------------------

    async def execute(self, payload: StudyRequest, trace_id: str = "unknown") -> StudyResult:
        """Execute a study request.

        Legacy adapter that bridges incoming StudyRequest payloads into the
        canonical ExecutionRequest contract, ensuring all requests pass through
        canonical governance and the native executor behind the orchestrator:
            API -> ExecutionRequest -> Canonical Execution Orchestrator -> StudyExecutor.execute_native.
        """
        self._validate_request(payload)

        # ETAP provider branch
        if payload.use_etap:
            start_wall = time.time()
            start_perf = time.perf_counter()
            data, warnings, errors = await self._run_etap_study(payload)
            data = self._to_jsonable(data)

            # Step 2: Executor Validation
            status = "failed" if errors else "success"
            validation_status = len(errors) == 0
            validation_report: dict[str, Any] = {}

            # Step 3: Canonical Engineering Validation on ETAP data (Phase 13 Authority)
            if status == "success" and data:
                from copilot.ai.engineering_assertions import EngineeringAssertionLayer

                assertion_layer = EngineeringAssertionLayer(strict_mode=False)
                report = assertion_layer.validate(data, payload.study_type)
                validation_status = report.passed
                validation_report = report.to_dict()
                if not report.passed or report.has_critical_failures:
                    crit_msgs = [
                        f.message
                        for f in report.failures
                        if f.severity.value in ("critical", "fatal")
                    ]
                    err_text = (
                        f"Engineering assertions blocked ETAP result: {len(crit_msgs)} violations detected."
                    )
                    errors.insert(0, err_text)
                    data["engineering_assertion_failures"] = [f.to_dict() for f in report.failures]
                    status = "failed"
                elif getattr(report, "warnings", []):
                    data["engineering_assertion_warnings"] = [f.to_dict() for f in report.warnings]
                    for w in report.warnings:
                        warnings.append(w.message)
            elif status != "success":
                validation_status = False

            # Step 4: Risk Assessment
            risk_info = compute_risk(payload.study_type, data) if data else {"risk_score": "low"}
            raw_risk_score = risk_info.get("risk_score", "low")
            risk_class = raw_risk_score if isinstance(raw_risk_score, str) else "low"
            risk_score_numeric = {
                "low": 0.1,
                "medium": 0.4,
                "high": 0.7,
                "critical": 1.0,
            }.get(risk_class, 0.0)

            # Step 5: Canonical Result (Phase 12)
            completed_wall = time.time()
            elapsed_sec = time.perf_counter() - start_perf
            task_id = payload.task_id or uuid.uuid4().hex

            cache_params = self._build_cache_params(
                payload,
                provider="etap",
                executor_kind="etap",
                solver="etap_solver",
                engine_version="etap_com",
            )

            provenance = {
                "execution_id": task_id,
                "request_id": None,
                "tenant_id": getattr(payload, "tenant_id", None),
                "provider": "etap",
                "executor_kind": "etap",
                "solver": "etap_solver",
                "engine_version": "etap_com",
                "trace_id": trace_id,
                "task_id": task_id,
                "timestamp": completed_wall,
                "validated_by": "EngineeringAssertionLayer",
            }

            return StudyResult(
                execution_id=task_id,
                request_id=None,
                tenant_id=getattr(payload, "tenant_id", None),
                capability_id=payload.study_type,
                capability_version="1.0.0",
                status="completed" if status == "success" else "failed",
                success=status == "success",
                provider="etap",
                executor_kind="etap",
                solver="etap_solver",
                engine_version="etap_com",
                input_snapshot_hash=cache_params.get("input_hash", ""),
                system_snapshot_hash=cache_params.get("system_snapshot_hash", ""),
                parameter_hash=cache_params.get("parameters_hash", ""),
                result=data,
                data=data,
                results=data,
                validation_status=validation_status,
                validation_report=validation_report,
                risk_class=risk_class,
                risk_score=risk_score_numeric,
                warnings=warnings,
                errors=errors,
                provenance=provenance,
                trace_id=trace_id,
                task_id=task_id,
                result_id=None,
                created_at=start_wall,
                completed_at=completed_wall,
                execution_time_sec=round(elapsed_sec, 3),
                study_type=payload.study_type,
            )

        req = ExecutionRequest.from_study_request(
            study_request=payload,
            trace_id=trace_id,
        )
        return self.execute_native(req)


    async def _run_native_study(self, payload: StudyRequest, trace_id: str) -> dict[str, Any]:
        cache = self._cache or self._init_cache()
        data, cache_hit = await self._lookup_cache(cache, payload, trace_id)
        if cache_hit:
            return data

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
        await self._store_cache_result(cache, payload, data, trace_id)
        return data

    def _apply_post_execution_checks(
        self, data: dict[str, Any], study_type: str, errors: list[str]
    ) -> str:
        status = "success"
        if is_feature_enabled("AI_FAILURE_MODE_SCAN"):
            violations = self._scan_ai_failure_modes(data, study_type)
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

        # Mandatory Engineering Assertions Layer (M5.2)
        # strict_mode=False contract:
        # - Only CRITICAL and FATAL violations block simulation results (status="failed").
        #   Blocking examples:
        #     * IEEE C84.1 Range B: voltage outside 0.916..1.083 pu (CRITICAL)
        #     * >200kA peak fault current: equipment withstand exceeded (FATAL)
        #     * Negative incident energy: unphysical arc flash calculation (FATAL)
        #     * Cable overload >200% ampacity: thermal burn danger (FATAL)
        #     * Protection selectivity margin <0.10s: breaker mis-coordination (CRITICAL)
        # - Non-critical failures (WARNING, INFO) are preserved in engineering_assertion_warnings
        #   and do NOT block completion (status stays "success").
        # Mandatory Engineering Assertions Layer (Canonical Engineering Validation - Phase 13 Authority)
        try:
            from copilot.ai.engineering_assertions import EngineeringAssertionLayer

            assertion_layer = EngineeringAssertionLayer(strict_mode=False)
            report = assertion_layer.validate(data, study_type)
            data["validation_status"] = report.passed
            data["validation_report"] = report.to_dict()

            if not report.passed or report.has_critical_failures:
                crit_msgs = [
                    f.message
                    for f in report.failures
                    if f.severity.value in ("critical", "fatal")
                ]
                max_sev = "fatal" if any(f.severity.value == "fatal" for f in report.failures) else "critical"
                err_text = (
                    f"Engineering assertions blocked result: {len(crit_msgs)} {max_sev.upper()} "
                    f"violations detected ({'; '.join(crit_msgs[:2])})."
                )
                errors.insert(0, err_text)
                data["engineering_assertion_failures"] = [f.to_dict() for f in report.failures]
                data["blocked_severity"] = max_sev
                status = "failed"
            elif getattr(report, "warnings", []):
                data["engineering_assertion_warnings"] = [f.to_dict() for f in report.warnings]
            elif report.failures:
                data["engineering_assertion_warnings"] = [f.to_dict() for f in report.failures]

            # V-04 (ADR-0003): Deterministic Engineering Assertion Layer on AI / fallback output
            if data.get("is_fallback") or data.get("fallback_model"):
                from copilot.ai.engineering_assertions import validate_fallback_output

                is_safe, fb_summary = validate_fallback_output(study_type, data, strict_mode=False)
                data["fallback_validation"] = fb_summary
                if not is_safe:
                    status = "failed"
                    errors.append(f"Fallback output validation failed for {study_type}.")
        except Exception as assertion_err:
            logger.warning("Engineering assertion execution error in StudyExecutor: %s", assertion_err)

        if status == "success":
            risk_info = compute_risk(study_type, data)
            data["risk_score"] = risk_info["risk_score"]
            data["risk_violations"] = risk_info["risk_violations"]

        return status

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_request(self, payload: StudyRequest) -> None:
        """Validate study type against active provider registry, feature flag, system requirement, and pre-flight checks."""
        # 1. Provider-aware study type validation against active registry
        if payload.use_etap:
            if payload.study_type not in _ETAP_STUDY_TYPE_MAP:
                raise ValueError(
                    f"Unknown or unsupported ETAP study type '{payload.study_type}'. "
                    f"Supported ETAP study types: {sorted(_ETAP_STUDY_TYPE_MAP.keys())}"
                )
        else:
            native_allowed = set(STUDY_DISPATCH.keys()) | set(_NATIVE_ALIASES.keys())
            if payload.study_type not in native_allowed:
                raise ValueError(
                    f"Unknown or unsupported native study type '{payload.study_type}'. "
                    f"Supported native study types: {sorted(native_allowed)}"
                )

        # 2. Feature flag check
        canonical_type = _NATIVE_ALIASES.get(payload.study_type, payload.study_type)
        flag_key = canonical_type if canonical_type in FEATURE_FLAGS else payload.study_type
        if flag_key in FEATURE_FLAGS and not is_feature_enabled(flag_key):
            flag_info = FEATURE_FLAGS.get(flag_key, {})
            raise ValueError(
                f"This study type is currently disabled in production. "
                f"Status: {flag_info.get('status', 'unknown')}. "
                f"Description: {flag_info.get('description', 'No description')}"
            )

        # 3. System model requirement
        if canonical_type in _TYPES_REQUIRING_SYSTEM and payload.system is None:
            raise ValueError(
                "System configuration is required. Please provide a valid power system model."
            )

        # 4. Pre-flight physics checks
        if payload.system is not None:
            pf_result = self._pre_flight_check(payload.system.model_dump())
            if pf_result is not None:
                raise ValueError(pf_result["error"])

    # ------------------------------------------------------------------
    # System building (moved from api/studies.py)
    # ------------------------------------------------------------------

    @staticmethod
    def _add_spec_buses(system: System, buses: list[Any]) -> dict[int, Bus]:
        bus_map: dict[int, Bus] = {}
        for b in buses:
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
        return bus_map

    @staticmethod
    def _add_spec_lines(system: System, lines: list[Any], bus_map: dict[int, Bus]) -> None:
        for l in lines:
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

    @staticmethod
    def _add_spec_transformers(
        system: System, transformers: list[Any], bus_map: dict[int, Bus]
    ) -> None:
        for t in transformers:
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

    @staticmethod
    def _add_spec_generators(
        system: System, generators: list[Any], bus_map: dict[int, Bus]
    ) -> None:
        for g in generators:
            if g.bus_id not in bus_map:
                raise ValueError(f"Generator {g.generator_id} references unknown bus")
            r1, x1 = g.r1, g.x1
            r2 = g.r2 if g.r2 is not None else r1
            x2 = g.x2 if g.x2 is not None else x1
            r0 = g.r0 if g.r0 is not None else r1
            x0 = g.x0 if g.x0 is not None else x1
            gen = Generator(
                generator_id=g.generator_id,
                bus=bus_map[g.bus_id],
                internal_voltage={
                    "1": complex(g.internal_voltage_mag, 0),
                    "2": complex(0, 0),
                    "0": complex(0, 0),
                },
                impedance={
                    "1": complex(r1, x1),
                    "2": complex(r2, x2),
                    "0": complex(r0, x0),
                },
            )
            system.add_generator(gen)

    @staticmethod
    def _add_spec_loads(
        system: System, loads: list[Any], bus_map: dict[int, Bus], base_mva: float
    ) -> None:
        for ld in loads:
            if ld.bus_id not in bus_map:
                raise ValueError(f"Load {ld.load_id} references unknown bus")
            load = Load(
                load_id=ld.load_id,
                bus=bus_map[ld.bus_id],
                load_power=complex(ld.p_mw / base_mva, ld.q_mvar / base_mva),
                constant_impedance=ld.constant_impedance,
            )
            system.add_load(load)

    def _build_system_from_spec(self, spec: Any) -> System:
        """Build a Python System object from a SystemSpec, dict, or System instance."""
        if isinstance(spec, System):
            return spec
        if isinstance(spec, dict):
            spec = SystemSpec.model_validate(spec)
        system = System(base_mva=spec.base_mva)
        bus_map = self._add_spec_buses(system, spec.buses)
        self._add_spec_lines(system, spec.lines, bus_map)
        self._add_spec_transformers(system, spec.transformers, bus_map)
        self._add_spec_generators(system, spec.generators, bus_map)
        self._add_spec_loads(system, spec.loads, bus_map, spec.base_mva)
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

        if canonical == "breaker_duty":
            from api.feature_flags import is_strict_feature_enabled

            if not is_strict_feature_enabled("breaker_duty"):
                raise SpecializedExecutionUnavailableError(
                    "breaker_duty", "Study type 'breaker_duty' is disabled by feature flag"
                )
            from breaker_duty.evaluator import BreakerDutyEvaluator

            return BreakerDutyEvaluator().execute_study(parameters)

        if canonical in ("ahmed_etap_orchestration", "ahmed_etap", "optimization"):
            return self._dispatch_agent(canonical, parameters)

        if registration.handler_type == "native":
            return self._dispatch_native(registration, system, parameters)
        if registration.handler_type == "agent":
            return self._dispatch_agent(canonical, parameters)
        raise SpecializedExecutionUnavailableError(
            canonical, f"handler_type '{registration.handler_type}' is external/not supported natively"
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
            tol = parameters.get("tol") or parameters.get("tolerance") or parameters.get("convergence_tolerance", 1e-6)
            max_iter = parameters.get("max_iter") or parameters.get("max_iterations", 100)
            mode = parameters.get("mode", "engineering")
            return method(tol=float(tol), max_iter=int(max_iter), mode=str(mode))
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
            relays_config = parameters.get("relays_config")
            if not relays_config:
                relays_config = {
                    "upstream": {"name": f"Relay_{upstream}", "tms": 0.5, "pickup_current_a": 100.0, "curve_type": "standard_inverse"},
                    "downstream": {"name": f"Relay_{downstream}", "tms": 0.2, "pickup_current_a": 50.0, "curve_type": "standard_inverse"},
                }
            return method(upstream, downstream, fault_currents, relays_config=relays_config)
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

        if study_type in ("ahmed_etap_orchestration", "ahmed_etap"):
            try:
                from agents.ahmed_etap_orchestrator import AhmedETAPSkillAgent
                from agents.models import EngineeringTask, StudyType
                from agents.orchestrator import get_orchestrator

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
            except Exception as exc:
                raise SpecializedExecutionUnavailableError(
                    study_type, f"Orchestrator execution unavailable: {exc}"
                ) from exc

        if study_type == "optimization":
            if not parameters:
                raise SpecializedExecutionUnavailableError(
                    study_type, "Study type 'optimization' requires specific parameters; empty parameters provided"
                )
            try:
                from agents.models import EngineeringTask, StudyType
                from agents.optimizers.optimization_agent import OptimizationAgent

                agent = OptimizationAgent()
                # Canonical mapping: 'optimization' study maps to OptimizationAgent with StudyType.OPTIMAL_POWER_FLOW
                # preserving the 17-member canonical StudyType specification per AGENTS.md / ADR-0001 without breaking compatibility.
                opt_task = EngineeringTask(
                    task_id=f"optimization_{int(time.time())}",
                    description=parameters.get("description", "Optimization study"),
                    study_types=[StudyType.OPTIMAL_POWER_FLOW],
                    parameters=parameters,
                )
                try:
                    asyncio.get_running_loop()
                    import concurrent.futures as _cf

                    with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                        result = pool.submit(lambda: asyncio.run(agent.execute(opt_task))).result()
                except RuntimeError:
                    result = asyncio.run(agent.execute(opt_task))

                if result.status.value != "completed":
                    err_detail = (
                        "; ".join(result.validation_errors)
                        if result.validation_errors
                        else result.data.get("error", "unknown error")
                    )
                    raise SpecializedExecutionUnavailableError(
                        study_type, f"Optimization execution failed: {err_detail}"
                    )
                return result.data
            except SpecializedExecutionUnavailableError:
                raise
            except Exception as exc:
                raise SpecializedExecutionUnavailableError(
                    study_type, f"Optimization execution unavailable: {exc}"
                ) from exc

        # Resolve across all registered specialized agents in canonical registry
        from agents.models import AgentStatus, EngineeringTask, StudyType
        from agents.registry import create_agent_registry, resolve_agent_key

        canonical_key = resolve_agent_key(study_type)
        try:
            agents = create_agent_registry()
        except Exception as exc:
            raise SpecializedExecutionUnavailableError(
                study_type, f"Agent registry creation failed: {exc}"
            ) from exc

        if canonical_key in agents:
            agent = agents[canonical_key]
            st_list: list[Any] = []
            try:
                st_list = [StudyType(canonical_key)]
            except ValueError:
                pass

            task = EngineeringTask(
                task_id=f"agent_task_{canonical_key}_{int(time.time() * 1000)}",
                description=f"Specialist agent execution for {study_type}",
                study_types=st_list,
                parameters=parameters,
            )
            try:
                if asyncio.iscoroutinefunction(getattr(agent, "execute", None)):
                    try:
                        asyncio.get_running_loop()
                        import concurrent.futures as _cf

                        with _cf.ThreadPoolExecutor(max_workers=1) as pool:
                            agent_res = pool.submit(lambda: asyncio.run(agent.execute(task))).result()
                    except RuntimeError:
                        agent_res = asyncio.run(agent.execute(task))
                else:
                    agent_res = agent.execute(task)

                status_enum = getattr(agent_res, "status", None)
                if status_enum == AgentStatus.FAILED or (
                    hasattr(status_enum, "value") and status_enum.value == "failed"
                ):
                    errs = getattr(agent_res, "validation_errors", []) or ["Agent execution failed"]
                    raise SpecializedExecutionUnavailableError(study_type, "; ".join(errs))

                return getattr(agent_res, "data", {}) or {}
            except SpecializedExecutionUnavailableError:
                raise
            except Exception as exc:
                raise SpecializedExecutionUnavailableError(
                    study_type, f"Agent execution failed for {study_type}: {exc}"
                ) from exc

        raise SpecializedExecutionUnavailableError(
            study_type, f"No agent registered for study type '{study_type}'"
        )

    # ------------------------------------------------------------------
    # ETAP provider
    # ------------------------------------------------------------------

    async def _run_etap_study(self, payload: StudyRequest) -> tuple[dict, list, list]:
        """Execute an ETAP study. Returns (data, warnings, errors)."""
        if not payload.etap_project_path:
            raise ValueError("etap_project_path is required when use_etap=True")

        from etap_integration.etap_provider import get_etap_provider

        provider = get_etap_provider()

        etap_study = _ETAP_STUDY_TYPE_MAP.get(payload.study_type)
        if etap_study is None:
            raise ValueError(f"No ETAP mapping for study type: {payload.study_type}")

        from compat import to_thread

        data = await to_thread(
            provider.execute_study,
            payload.etap_project_path,
            etap_study,
        )
        # provider.execute_study() returns an ETAPResult object (not a dict).
        # Use getattr() to safely extract its attributes.
        warnings = list(getattr(data, "warnings", []) or [])
        errors = list(getattr(data, "errors", []) or [])
        if not getattr(data, "success", True):
            errors.append("ETAP study reported failure")
        # ETAPResult stores the actual payload in .data (dict), fallback to .results for legacy objects
        payload_dict = getattr(data, "data", None) or getattr(data, "results", None) or {}
        return payload_dict, warnings, errors

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

    def _build_cache_params(
        self,
        payload: Any = None,
        provider: str = "native",
        executor_kind: str = "native",
        solver: str = "",
        engine_version: str = "2.1.0",
        capability_version: str = "1.0.0",
        standards: Any = "default",
        *,
        capability_id: Optional[str] = None,
        system_snapshot_hash: Optional[str] = None,
        input_hash: Optional[str] = None,
        parameters_hash: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Construct multi-dimensional cache identity and input hashes (Phase 14).

        Distinguishes at minimum:
        capability_id, capability_version, executor_kind, provider, solver/engine,
        engine_version, system_snapshot_hash, input_hash, parameters_hash, and standards.
        Ensures native and ETAP executions never accidentally reuse one another's results.
        """
        resolved_capability_id = (
            capability_id
            or getattr(payload, "capability_id", None)
            or getattr(payload, "study_type", "")
            or ""
        )
        # Detect ETAP from payload if not explicitly overridden
        if getattr(payload, "use_etap", False) and provider == "native":
            provider = "etap"
            executor_kind = "etap"
            solver = solver or "etap_solver"
            engine_version = "etap_com"

        solver_name = solver or (
            "newton_raphson"
            if resolved_capability_id == "load_flow" and provider == "native"
            else (provider or "default")
        )
        raw_params = getattr(payload, "parameters", {}) or {}
        if parameters_hash is not None:
            resolved_params_hash = parameters_hash
        else:
            params_json = json.dumps(raw_params, sort_keys=True, default=str)
            resolved_params_hash = hashlib.sha256(params_json.encode()).hexdigest()

        # System model snapshot hash
        if system_snapshot_hash is not None:
            resolved_sys_hash = system_snapshot_hash
        else:
            system_obj = getattr(payload, "system", None)
            resolved_sys_hash = ""
            if system_obj is not None:
                if hasattr(system_obj, "model_dump"):
                    sys_dict = system_obj.model_dump()
                elif isinstance(system_obj, dict):
                    sys_dict = system_obj
                else:
                    sys_dict = str(system_obj)
                system_json = json.dumps(sys_dict, sort_keys=True, default=str)
                resolved_sys_hash = hashlib.sha256(system_json.encode()).hexdigest()

        # Input snapshot hash
        if input_hash is not None:
            resolved_input_hash = input_hash
        else:
            input_payload = {
                "capability_id": resolved_capability_id,
                "provider": provider,
                "executor_kind": executor_kind,
                "solver": solver_name,
                "engine_version": engine_version,
                "parameters": raw_params,
                "system_hash": resolved_sys_hash,
                "standards": standards,
            }
            input_json = json.dumps(input_payload, sort_keys=True, default=str)
            resolved_input_hash = hashlib.sha256(input_json.encode()).hexdigest()

        return {
            "capability_id": resolved_capability_id,
            "capability_version": capability_version,
            "executor_kind": executor_kind,
            "provider": provider,
            "solver": solver_name,
            "engine_version": engine_version,
            "system_snapshot_hash": resolved_sys_hash,
            "input_hash": resolved_input_hash,
            "parameters_hash": resolved_params_hash,
            "standards": standards,
            # Backward-compatibility keys
            "study_type": resolved_capability_id,
            "parameters": raw_params,
            "system_hash": resolved_sys_hash,
        }

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

    def _convert_numpy_value(self, obj: Any) -> tuple[bool, Any]:
        import numpy as np

        if isinstance(obj, np.ndarray):
            return True, [self._to_jsonable(x) for x in obj.tolist()]
        if isinstance(obj, (np.integer,)):
            return True, int(obj.item())
        if isinstance(obj, (np.floating,)):
            v = float(obj.item())
            return True, None if (math.isnan(v) or math.isinf(v)) else v
        if isinstance(obj, (np.bool_,)):
            return True, bool(obj.item())
        if isinstance(obj, np.complexfloating):
            return True, {"real": self._to_jsonable(obj.real), "imag": self._to_jsonable(obj.imag)}
        return False, None

    def _to_jsonable(self, obj: Any) -> Any:
        """Recursively convert numpy types and other non-JSON-native values."""
        if obj is None or isinstance(obj, (str, bool)):
            return obj
        if isinstance(obj, (int, float)):
            return (
                None if (isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj))) else obj
            )
        if isinstance(obj, complex):
            return {"re": self._to_jsonable(obj.real), "im": self._to_jsonable(obj.imag)}

        converted, val = self._convert_numpy_value(obj)
        if converted:
            return val

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

    def _pre_flight_units(self, system: dict) -> Optional[dict]:
        """Validate explicit units on system elements (buses, lines, parameters) for physical dimension consistency."""
        try:
            from core.units import validate_parameter_dimension
        except ImportError:
            return None

        # Check buses
        for bus in system.get("buses", []):
            bus_id = bus.get("bus_id", "unknown")
            v_val = bus.get("base_kv") or bus.get("voltage_kv") or bus.get("nominal_voltage")
            if v_val is not None:
                valid, err = validate_parameter_dimension("voltage_setpoint", v_val)
                if not valid:
                    return {"error": f"Bus {bus_id} voltage dimension mismatch: {err}"}

        # Check lines
        for line in system.get("lines", []):
            line_id = line.get("line_id", "unknown")
            for param in ("r1", "x1", "r0", "x0"):
                val = line.get(param)
                if val is not None:
                    valid, err = validate_parameter_dimension("transformer_impedance", val)
                    if not valid:
                        return {"error": f"Line {line_id} parameter '{param}' dimension mismatch: {err}"}

        # Check top-level engineering parameters if present in system dictionary
        for key, val in system.items():
            if key in ("buses", "lines", "transformers", "loads", "generators"):
                continue
            valid, err = validate_parameter_dimension(key, val)
            if not valid:
                return {"error": f"System parameter '{key}' dimension mismatch: {err}"}

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
        result = self._pre_flight_voltage_bounds(buses)
        if result is not None:
            return result
        return self._pre_flight_units(system)

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
