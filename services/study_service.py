"""
Study Service module for the Engineering Service.
Handles all study execution logic, system building, and ETAP integration.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Coroutine
from typing import Any, TypeVar

from core.bootstrap import _get_etap_provider, _get_power_system_engine, logger
from core.exceptions import SpecializedExecutionUnavailableError
from core.tracing import trace_operation

# ---------------------------------------------------------------------------
# Pydantic schemas — shared canonical definitions.
# SonarCloud duplicated_lines_density: all Spec/Request/Result classes are
# defined ONCE in core_model/specs.py and imported here. The previous local
# definitions were ~210 lines of byte-identical duplication between this file
# and api/studies.py.
# ---------------------------------------------------------------------------
from core_model.specs import (
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


# ---------------------------------------------------------------------------
# System builder helper
# ---------------------------------------------------------------------------


@trace_operation("_build_system_from_spec", attributes={"component": "engineering_service"})
def _build_system_from_spec(  # NOSONAR
    spec: SystemSpec,
) -> Any:  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
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
        if l.from_bus_id not in bus_map:
            logger.warning(
                "Line %s references unknown from_bus %s, creating default PQ bus",
                l.line_id,
                l.from_bus_id,
            )
            bus = Bus(bus_id=l.from_bus_id, bus_type="pq")
            system.add_bus(bus)
            bus_map[l.from_bus_id] = bus
        if l.to_bus_id not in bus_map:
            logger.warning(
                "Line %s references unknown to_bus %s, creating default PQ bus",
                l.line_id,
                l.to_bus_id,
            )
            bus = Bus(bus_id=l.to_bus_id, bus_type="pq")
            system.add_bus(bus)
            bus_map[l.to_bus_id] = bus
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
        if t.from_bus_id not in bus_map:
            logger.warning(
                "Transformer %s references unknown from_bus %s, creating default PQ bus",
                t.transformer_id,
                t.from_bus_id,
            )
            bus = Bus(bus_id=t.from_bus_id, bus_type="pq")
            system.add_bus(bus)
            bus_map[t.from_bus_id] = bus
        if t.to_bus_id not in bus_map:
            logger.warning(
                "Transformer %s references unknown to_bus %s, creating default PQ bus",
                t.transformer_id,
                t.to_bus_id,
            )
            bus = Bus(bus_id=t.to_bus_id, bus_type="pq")
            system.add_bus(bus)
            bus_map[t.to_bus_id] = bus
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
            logger.warning(
                "Generator %s references unknown bus %s, creating default PV bus",
                g.generator_id,
                g.bus_id,
            )
            bus = Bus(bus_id=g.bus_id, bus_type="pv")
            system.add_bus(bus)
            bus_map[g.bus_id] = bus
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
            logger.warning(
                "Load %s references unknown bus %s, creating default PQ bus",
                ld.load_id,
                ld.bus_id,
            )
            bus = Bus(bus_id=ld.bus_id, bus_type="pq")
            system.add_bus(bus)
            bus_map[ld.bus_id] = bus
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

_STUDIES_REQUIRING_SYSTEM = {
    "load_flow",
    "short_circuit",
    "fault",
    "fault_analysis",
    "protection_coordination",
    "coordination",
    "motor_starting",
}


T = TypeVar("T")


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine safely, whether or not an event loop is active."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # We're inside an async context - create a new loop in a thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


@trace_operation("_run_native_study", attributes={"component": "engineering_service"})
def _run_native_study(  # NOSONAR cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    study_type: str,
    system: Any | None,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """
    [LEGACY COMPATIBILITY ONLY]
    Execute a study using the legacy direct PowerSystemEngine invocation.

    WARNING: This function is quarantined for legacy test compatibility only.
    All production code MUST execute studies via ExecutionOrchestrator and
    StudyExecutor._dispatch() conforming to the Canonical Execution Flow.
    Direct invocation of _run_native_study is deprecated and subject to removal.
    """
    import warnings
    warnings.warn(
        "_run_native_study is quarantined for legacy compatibility and deprecated. "
        "Use ExecutionOrchestrator or StudyExecutor instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.warning(
        "[LEGACY_QUARANTINE] services.study_service._run_native_study called for study_type='%s'. "
        "Production paths must route through ExecutionOrchestrator.",
        study_type,
    )
    if study_type in _STUDIES_REQUIRING_SYSTEM and system is None:
        raise ValueError(f"study_type '{study_type}' requires a 'system' to be provided")

    Engine = _get_power_system_engine()  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    engine = Engine(system)

    if study_type in ("load_flow",):
        tol = parameters.get("tol") or parameters.get("tolerance") or parameters.get("convergence_tolerance", 1e-6)
        max_iter = parameters.get("max_iter") or parameters.get("max_iterations", 100)
        mode = parameters.get("mode", "engineering")
        raw_res = engine.run_load_flow(tol=float(tol), max_iter=int(max_iter), mode=str(mode))
    elif study_type in ("short_circuit", "fault", "fault_analysis"):
        fault_type = parameters.get("fault_type", "three_phase")
        bus_id = parameters.get("bus_id")
        if bus_id is None:
            if engine.load_flow_solver and engine.load_flow_solver.bus_ids:
                bus_id = engine.load_flow_solver.bus_ids[0]
            else:
                raise ValueError("bus_id is required for fault analysis")
        raw_res = engine.run_fault_analysis(fault_type, bus_id)
    elif study_type == "arc_flash":
        # Provide fallback defaults for missing parameters to allow basic execution/testing
        if "voltage_kv" not in parameters:
            parameters["voltage_kv"] = 13.8
        if "bolted_fault_current_ka" not in parameters:
            parameters["bolted_fault_current_ka"] = 20.0
        if "arc_duration_sec" not in parameters:
            parameters["arc_duration_sec"] = 0.1
        if "working_distance_mm" not in parameters:
            parameters["working_distance_mm"] = 610.0
        raw_res = engine.run_arc_flash(
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
        raw_res = engine.run_protection_coordination(upstream, downstream, fault_currents)
    else:
        raise SpecializedExecutionUnavailableError(
            study_type, f"Unsupported native study type: {study_type}"
        )

    if isinstance(raw_res, dict):
        raw_res["execution_path"] = "LEGACY_NON_AUTHORITATIVE"
        raw_res["authoritative"] = False
    return raw_res



@trace_operation("_run_etap_study", attributes={"component": "engineering_service"})
def _run_etap_study(
    study_type: str,
    project_path: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """
    [LEGACY COMPATIBILITY ONLY]
    Execute a study via the legacy ETAP provider directly.

    WARNING: This function is quarantined for legacy test compatibility only.
    All production code MUST execute studies via ExecutionOrchestrator and
    StudyExecutor._dispatch() conforming to the Canonical Execution Flow.
    Direct invocation of _run_etap_study is deprecated and subject to removal.
    """
    import warnings
    warnings.warn(
        "_run_etap_study is quarantined for legacy compatibility and deprecated. "
        "Use ExecutionOrchestrator or StudyExecutor instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.warning(
        "[LEGACY_QUARANTINE] services.study_service._run_etap_study called for study_type='%s'. "
        "Production paths must route through ExecutionOrchestrator.",
        study_type,
    )
    # Check if ETAP is enabled
    if os.getenv("USE_ETAP", "false").lower() != "true":
        raise RuntimeError("ETAP functionality is disabled via USE_ETAP environment variable")

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


def execute_study_logic(  # NOSONAR
    payload: StudyRequest,
    trace_id: str,
    start_time: float,
    execution_request: Any | None = None,
) -> StudyResult:
    """Execute study logic routed canonically through ExecutionOrchestrator."""
    from api.request_context import get_tenant_id
    from core.bootstrap import _add_execution_time, _increment_counter
    from services.execution_orchestrator import get_execution_orchestrator
    from services.execution_request import ExecutionRequest
    from utils.language_detection import normalize_input

    task_id = payload.task_id or f"task_{int(time.time())}"

    # Enable auto-correct for non-English input
    auto_correct = os.getenv("AUTO_CORRECT_LANGUAGE", "true").lower() == "true"
    if auto_correct and payload.parameters:
        payload.parameters = {k: normalize_input(str(v)) for k, v in payload.parameters.items()}

    _increment_counter("request")
    logger.info(
        "study_run_start study_type=%s use_etap=%s task_id=%s",
        payload.study_type,
        payload.use_etap,
        task_id,
        extra={"trace_id": trace_id},
    )

    tenant_id = (
        get_tenant_id()
        or getattr(payload, "tenant_id", None)
        or (execution_request.tenant_id if execution_request else None)
        or "service_tenant_worker"
    )
    user_id = (
        getattr(payload, "user_id", None)
        or (execution_request.user_id if execution_request else None)
        or "service_principal:worker"
    )

    if execution_request is None:
        execution_request = ExecutionRequest.from_study_request(
            study_request=payload,
            user_id=user_id,
            tenant_id=tenant_id,
            user_role="engineer",
            trace_id=trace_id,
        )

    orchestrator = get_execution_orchestrator()
    try:
        canonical_res = _run_async(orchestrator.execute(execution_request))
        study_res = canonical_res.to_study_result(study_type=payload.study_type)
    except Exception as exc:
        logger.exception("Canonical study execution failed in study_service: %s", exc)
        study_res = StudyResult(
            study_type=payload.study_type,
            success=False,
            data={},
            results={},
            errors=[str(exc)],
            warnings=[],
            trace_id=trace_id,
            task_id=task_id,
            provider="native",
        )

    elapsed_sec = time.perf_counter() - start_time
    _add_execution_time(elapsed_sec)
    _increment_counter("success" if study_res.success else "failed")

    logger.info(
        "study_run_end study_type=%s status=%s elapsed_sec=%.3f task_id=%s",
        payload.study_type,
        study_res.status,
        elapsed_sec,
        task_id,
        extra={"trace_id": trace_id},
    )

    return study_res
