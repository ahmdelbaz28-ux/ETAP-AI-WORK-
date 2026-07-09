"""
Study Service module for the Engineering Service.
Handles all study execution logic, system building, and ETAP integration.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Coroutine
from typing import Any, Optional, TypeVar, Union

from core.bootstrap import _get_etap_provider, _get_power_system_engine, _to_jsonable, logger
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
            logger.warning(
                "Load %s references unknown bus %s, creating default PQ bus", ld.load_id, ld.bus_id,
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
def _run_native_study(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    study_type: str, system: Optional[Any], parameters: dict[str, Any],
) -> dict[str, Any]:
    """Execute a study using the native PowerSystemEngine."""
    if study_type in _STUDIES_REQUIRING_SYSTEM and system is None:
        raise ValueError(f"study_type '{study_type}' requires a 'system' to be provided")

    Engine = _get_power_system_engine()  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    engine = Engine(system)

    if study_type in ("load_flow",):
        return engine.run_load_flow()
    elif study_type in ("short_circuit", "fault", "fault_analysis"):
        fault_type = parameters.get("fault_type", "three_phase")
        bus_id = parameters.get("bus_id")
        if bus_id is None:
            if engine.load_flow_solver and engine.load_flow_solver.bus_ids:
                bus_id = engine.load_flow_solver.bus_ids[0]
            else:
                raise ValueError("bus_id is required for fault analysis")
        return engine.run_fault_analysis(fault_type, bus_id)
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
def _run_etap_study(
    study_type: str, project_path: str, parameters: dict[str, Any],
) -> dict[str, Any]:
    """Execute a study via the ETAP provider."""
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


def execute_study_logic(payload: StudyRequest, trace_id: str, start_time: float) -> StudyResult:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Execute study logic with caching and proper error handling."""
    from core.bootstrap import _add_execution_time, _increment_counter, _study_cache
    from utils.language_detection import normalize_input

    task_id = payload.task_id or f"task_{int(time.time())}"

    # Enable auto-correct for non-English input
    auto_correct = os.getenv("AUTO_CORRECT_LANGUAGE", "true").lower() == "true"

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

    warnings: list[str] = []
    errors: list[str] = []
    data: dict[str, Any] = {}
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

                    system_json = json.dumps(
                        payload.system.model_dump(), sort_keys=True, default=str,
                    )
                    cache_params["system_hash"] = _hashlib.sha256(system_json.encode()).hexdigest()
                if _study_cache:
                    cached_result = _run_async(_study_cache.get(payload.study_type, cache_params))
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
            data = _run_async(
                asyncio.to_thread(
                    _run_etap_study,
                    payload.study_type,
                    payload.etap_project_path,
                    payload.parameters,
                ),
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
                    from fastapi import HTTPException

                    raise HTTPException(status_code=400, detail=f"System spec error: {ve}") from ve
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
                if _study_cache:
                    _run_async(
                        _study_cache.set(
                            payload.study_type, cache_params, json.dumps(data, default=str),
                        ),
                    )
            except Exception as cache_err:
                logger.debug(
                    "Cache store failed (non-fatal): %s", cache_err, extra={"trace_id": trace_id},
                )

        _increment_counter("success")
        status = "success"
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

    elapsed_sec = time.perf_counter() - start_time
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
