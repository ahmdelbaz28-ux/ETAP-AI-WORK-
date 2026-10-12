"""ETAP Draw Plan Builder.

Constructs dependency-ordered, chunked drawing requests for the ETAP REST API
(ETAP DataHub etapAPI).

Responsibilities:
1. Normalizes diverse electrical models (core_model.System, sync_engine dicts, Zenon dicts)
2. Enforces topological dependency ordering:
   Buses -> Transformers -> Switchgear (Breakers/Switches) -> Branches/Loads
3. Partitions into atomic chunks of <= 50 elements (etapAPI limit)
4. Verifies topological connectivity before dispatching draw requests
5. Coordinates atomic multi-chunk execution with automatic rollback on failure
6. Enforces zero guessing: rejects incomplete data fail-closed with INCOMPLETE_DATA.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Optional

from core_model.system import System
from etap_integration.etap_rest import (
    MAX_ELEMENTS_PER_REQUEST,
    DrawResult,
    EtapDrawPlan,
    EtapElement,
    EtapRestClient,
    ETAPRestError,
)

logger = logging.getLogger(__name__)


def build_draw_plan(
    model: Any,
    project_id: str,
    max_items: int = MAX_ELEMENTS_PER_REQUEST,
    extra_known_buses: set[str] | None = None,
    allow_incomplete: bool = False,
    reason: str | None = None,
) -> list[EtapDrawPlan]:
    """Transforms an electrical model into dependency-ordered EtapDrawPlan chunks.

    Parameters
    ----------
    model : System or dict
        Internal electrical model or dictionary of components.
    project_id : str
        Target ETAP project ID.
    max_items : int
        Maximum elements per chunk (<= 50).
    extra_known_buses : set[str], optional
        Buses already confirmed present in the target project.
    allow_incomplete : bool
        If False, missing mandatory properties raise ETAPRestError('INCOMPLETE_DATA').
    reason : str, optional
        Custom description or reason for the draw plan.

    Returns
    -------
    list[EtapDrawPlan]
        List of validated draw plans ready for sequential execution.
    """
    if not project_id or not str(project_id).strip():
        raise ETAPRestError("INVALID_PROJECT", "project_id must not be empty.")

    chunk_size = min(max_items, MAX_ELEMENTS_PER_REQUEST)
    if chunk_size <= 0:
        chunk_size = MAX_ELEMENTS_PER_REQUEST

    # 1. Normalize model into standard component dictionaries
    components = _normalize_model_components(model, allow_incomplete=allow_incomplete)

    # 2. Extract and validate topological connectivity
    known_buses: set[str] = set(extra_known_buses or set())
    for b in components["buses"]:
        b_id = str(b.get("id") or b.get("name") or "").strip()
        if b_id:
            known_buses.add(b_id)
        name = str(b.get("name") or "").strip()
        if name:
            known_buses.add(name)

    _validate_connectivity(components, known_buses)

    # 3. Build EtapElement objects per layer
    bus_elements = _build_bus_elements(components["buses"], allow_incomplete=allow_incomplete)
    xf_elements = _build_transformer_elements(
        components["transformers"], allow_incomplete=allow_incomplete
    )
    switchgear_elements = _build_switchgear_elements(
        components.get("breakers", []),
        components.get("switches", []),
        allow_incomplete=allow_incomplete,
    )
    branch_and_load_elements = _build_branch_and_load_elements(
        lines=components.get("lines", []),
        cables=components.get("cables", []),
        loads=components.get("loads", []),
        generators=components.get("generators", []),
        motors=components.get("motors", []),
        capacitors=components.get("capacitors", []),
        reactors=components.get("reactors", []),
        relays=components.get("relays", []),
        allow_incomplete=allow_incomplete,
    )

    # Mandatory ordering: buses -> transformers -> switchgear -> branches/loads
    ordered_elements: list[EtapElement] = (
        bus_elements + xf_elements + switchgear_elements + branch_and_load_elements
    )

    if not ordered_elements:
        logger.warning("build_draw_plan: model has no electrical elements to draw.")
        return []

    # 4. Partition into chunks <= chunk_size
    chunks: list[list[EtapElement]] = [
        ordered_elements[i : i + chunk_size] for i in range(0, len(ordered_elements), chunk_size)
    ]

    total_chunks = len(chunks)
    plans: list[EtapDrawPlan] = []
    default_reason_prefix = reason or f"Draw network for project {project_id}"
    for idx, chunk in enumerate(chunks):
        plan = EtapDrawPlan(
            project_id=project_id,
            items=chunk,
            delete_ids=[],
            reason=f"{default_reason_prefix} (chunk {idx + 1}/{total_chunks})",
        )
        plans.append(plan)

    logger.info(
        "Built %d EtapDrawPlan chunks (%d total elements) for project %s",
        len(plans),
        len(ordered_elements),
        project_id,
    )
    return plans


async def execute_draw_plans_atomic(
    client: EtapRestClient,
    plans: list[EtapDrawPlan],
    on_chunk_completed: Optional[Callable[[int, DrawResult, list[str]], Awaitable[None]]] = None,
) -> list[DrawResult]:
    """Executes a sequence of EtapDrawPlan chunks with atomic rollback on any failure."""
    if not plans:
        return []

    project_id = plans[0].project_id
    all_created_ids: list[str] = []
    results: list[DrawResult] = []

    for idx, plan in enumerate(plans):
        logger.info(
            "Executing ETAP draw chunk %d/%d (%d items) on project %s",
            idx + 1,
            len(plans),
            len(plan.items),
            project_id,
        )
        try:
            res = await client.apply_draw(plan)
            all_created_ids.extend(res.created_ids)
            results.append(res)
            if on_chunk_completed is not None:
                cb_res = on_chunk_completed(idx, res, list(all_created_ids))
                import inspect

                if inspect.isawaitable(cb_res):
                    await cb_res
        except Exception as exc:
            logger.error(
                "Chunk %d/%d failed: %s. Initiating atomic rollback of %d previously created elements.",
                idx + 1,
                len(plans),
                exc,
                len(all_created_ids),
            )
            # Rollback all previously created elements in batches of 50
            if all_created_ids:
                for b_start in range(0, len(all_created_ids), MAX_ELEMENTS_PER_REQUEST):
                    batch = all_created_ids[b_start : b_start + MAX_ELEMENTS_PER_REQUEST]
                    try:
                        await client.delete_elements(project_id, batch)
                    except Exception as rb_err:
                        logger.warning("Rollback deletion batch failed: %s", rb_err)

            error_msg = f"Multi-chunk ETAP draw failed at chunk {idx + 1}/{len(plans)}: {exc}"
            raise ETAPRestError(
                code="DRAW_CHUNK_FAILED",
                message=error_msg,
                details={
                    "failed_chunk_index": idx + 1,
                    "total_chunks": len(plans),
                    "rolled_back_ids": all_created_ids,
                },
            ) from exc

    return results


# ---------------------------------------------------------------------------
# Internal Normalization and Validation Helpers
# ---------------------------------------------------------------------------


def _normalize_model_components(
    model: Any,
    allow_incomplete: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Converts a System, sync_engine dict, or Zenon dict into uniform component lists."""
    components: dict[str, list[dict[str, Any]]] = {
        "buses": [],
        "transformers": [],
        "lines": [],
        "cables": [],
        "breakers": [],
        "switches": [],
        "loads": [],
        "generators": [],
        "motors": [],
        "capacitors": [],
        "reactors": [],
        "relays": [],
    }

    if isinstance(model, System):
        # Extract from core_model.System
        for bid, b in model.buses.items():
            base_kv = getattr(b, "base_kv", None)
            if base_kv is None and not allow_incomplete:
                raise ETAPRestError(
                    "INCOMPLETE_DATA",
                    f"Bus '{b.bus_id}' missing mandatory field 'base_kv'",
                    {"element": str(b.bus_id), "field": "base_kv"},
                )
            components["buses"].append(
                {
                    "id": str(bid),
                    "name": str(b.bus_id),
                    "base_kv": base_kv,
                }
            )
        for xf in model.transformers:
            components["transformers"].append(
                {
                    "id": str(xf.transformer_id),
                    "name": f"XF_{xf.transformer_id}",
                    "from_bus": str(xf.from_bus.bus_id),
                    "to_bus": str(xf.to_bus.bus_id),
                    "rating_mva": getattr(xf, "rating", None),
                    "r_pu": getattr(xf, "r_pu", None)
                    or (xf.z1.real if hasattr(xf, "z1") else None),
                    "x_pu": getattr(xf, "x_pu", None)
                    or (xf.z1.imag if hasattr(xf, "z1") else None),
                    "tap_ratio": getattr(xf, "tap_ratio", None),
                }
            )
        for ln in model.lines:
            rating_mva = getattr(ln, "rating", None)
            if rating_mva is None and not allow_incomplete:
                raise ETAPRestError(
                    "INCOMPLETE_DATA",
                    f"Line '{ln.line_id}' missing mandatory field 'rating_mva'",
                    {"element": str(ln.line_id), "field": "rating_mva"},
                )
            components["lines"].append(
                {
                    "id": str(ln.line_id),
                    "name": f"LINE_{ln.line_id}",
                    "from_bus": str(ln.from_bus.bus_id),
                    "to_bus": str(ln.to_bus.bus_id),
                    "r_pu": ln.z1.real,
                    "x_pu": ln.z1.imag,
                    "rating_mva": rating_mva,
                }
            )
        for ld in model.loads:
            base_mva = model.base_mva or 1.0
            components["loads"].append(
                {
                    "id": str(ld.load_id),
                    "name": f"LOAD_{ld.load_id}",
                    "bus": str(ld.bus.bus_id),
                    "p_mw": ld.load_power.real * base_mva,
                    "q_mvar": ld.load_power.imag * base_mva,
                }
            )
        for gen in model.generators:
            components["generators"].append(
                {
                    "id": str(gen.generator_id),
                    "name": f"GEN_{gen.generator_id}",
                    "bus": str(gen.bus.bus_id),
                    "rating_mva": getattr(gen, "rating_mva", None)
                    or (gen.max_power.real if hasattr(gen, "max_power") else None),
                }
            )
        return components

    if isinstance(model, dict):
        # Already a dictionary of components
        for key in components:
            raw_list = model.get(key) or model.get("objects", {}).get(key) or []
            if isinstance(raw_list, list):
                components[key] = list(raw_list)
        return components

    raise ETAPRestError(
        "UNSUPPORTED_MODEL_TYPE",
        f"Cannot build draw plan from model type {type(model)}",
    )


def _validate_connectivity(
    components: dict[str, list[dict[str, Any]]],
    known_buses: set[str],
) -> None:
    """Ensures all branch components connect exclusively to existing buses."""
    # Two-terminal checks
    for kind, items in [
        ("transformer", components.get("transformers", [])),
        ("line", components.get("lines", [])),
        ("cable", components.get("cables", [])),
        ("breaker", components.get("breakers", [])),
        ("switch", components.get("switches", [])),
        ("reactor", components.get("reactors", [])),
    ]:
        for it in items:
            name = it.get("name") or it.get("id") or "UNKNOWN"
            from_b = str(it.get("from_bus") or "").strip()
            to_b = str(it.get("to_bus") or "").strip()

            if from_b and from_b not in known_buses:
                raise ETAPRestError(
                    "INVALID_TOPOLOGY",
                    f"Component '{name}' ({kind}) references missing from_bus '{from_b}'",
                    {"element": name, "missing_bus": from_b},
                )
            if to_b and to_b not in known_buses:
                raise ETAPRestError(
                    "INVALID_TOPOLOGY",
                    f"Component '{name}' ({kind}) references missing to_bus '{to_b}'",
                    {"element": name, "missing_bus": to_b},
                )

    # Single-terminal checks
    for kind, items in [
        ("load", components.get("loads", [])),
        ("generator", components.get("generators", [])),
        ("motor", components.get("motors", [])),
        ("capacitor", components.get("capacitors", [])),
        ("relay", components.get("relays", [])),
    ]:
        for it in items:
            name = it.get("name") or it.get("id") or "UNKNOWN"
            bus = str(it.get("bus") or "").strip()
            if bus and bus not in known_buses:
                raise ETAPRestError(
                    "INVALID_TOPOLOGY",
                    f"Component '{name}' ({kind}) references missing bus '{bus}'",
                    {"element": name, "missing_bus": bus},
                )


# ---------------------------------------------------------------------------
# Element Construction Helpers
# ---------------------------------------------------------------------------


def _build_bus_elements(
    buses: list[dict[str, Any]],
    allow_incomplete: bool = False,
) -> list[EtapElement]:
    elements: list[EtapElement] = []
    for b in buses:
        name = str(b.get("name") or b.get("id") or "BUS")
        kv = b.get("base_kv") if b.get("base_kv") is not None else b.get("voltage_kv")
        if kv is None and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Bus '{name}' is missing mandatory 'base_kv'",
                {"element": name, "field": "base_kv"},
            )
        elements.append(
            EtapElement(
                element_type="bus",
                name=name,
                properties={"name": name, "base_kv": float(kv) if kv is not None else None},
            )
        )
    return elements


def _build_transformer_elements(
    transformers: list[dict[str, Any]],
    allow_incomplete: bool = False,
) -> list[EtapElement]:
    elements: list[EtapElement] = []
    for xf in transformers:
        name = str(xf.get("name") or xf.get("id") or "XF")
        from_b = str(xf.get("from_bus") or "").strip()
        to_b = str(xf.get("to_bus") or "").strip()
        if (not from_b or not to_b) and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Transformer '{name}' is missing mandatory terminal buses (from_bus='{from_b}', to_bus='{to_b}')",
                {
                    "element": name,
                    "missing": [k for k, v in [("from_bus", from_b), ("to_bus", to_b)] if not v],
                },
            )
        props: dict[str, Any] = {
            "name": name,
            "from_bus": from_b,
            "to_bus": to_b,
        }
        for prop_key in (
            "rating_mva",
            "prim_kv",
            "sec_kv",
            "r_pu",
            "x_pu",
            "tap_ratio",
            "vector_group",
        ):
            if xf.get(prop_key) is not None:
                val = xf[prop_key]
                if prop_key in ("rating_mva", "prim_kv", "sec_kv", "r_pu", "x_pu", "tap_ratio"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[prop_key] = val
        elements.append(
            EtapElement(
                element_type="transformer",
                name=name,
                properties=props,
            )
        )
    return elements


def _build_switchgear_elements(
    breakers: list[dict[str, Any]],
    switches: list[dict[str, Any]],
    allow_incomplete: bool = False,
) -> list[EtapElement]:
    elements: list[EtapElement] = []
    for brk in breakers:
        name = str(brk.get("name") or brk.get("id") or "CB")
        from_b = str(brk.get("from_bus") or "").strip()
        to_b = str(brk.get("to_bus") or "").strip()
        if (not from_b or not to_b) and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Breaker '{name}' is missing mandatory terminal buses (from_bus='{from_b}', to_bus='{to_b}')",
                {
                    "element": name,
                    "missing": [k for k, v in [("from_bus", from_b), ("to_bus", to_b)] if not v],
                },
            )
        props: dict[str, Any] = {"name": name, "from_bus": from_b, "to_bus": to_b}
        if brk.get("status") is not None:
            props["status"] = str(brk["status"])
        if brk.get("rated_a") is not None:
            props["rated_a"] = float(brk["rated_a"])
        if brk.get("breaking_capacity_ka") is not None:
            props["breaking_capacity_ka"] = float(brk["breaking_capacity_ka"])
        elements.append(
            EtapElement(
                element_type="breaker",
                name=name,
                properties=props,
            )
        )

    for sw in switches:
        name = str(sw.get("name") or sw.get("id") or "SW")
        from_b = str(sw.get("from_bus") or "").strip()
        to_b = str(sw.get("to_bus") or "").strip()
        if (not from_b or not to_b) and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Switch '{name}' is missing mandatory terminal buses (from_bus='{from_b}', to_bus='{to_b}')",
                {
                    "element": name,
                    "missing": [k for k, v in [("from_bus", from_b), ("to_bus", to_b)] if not v],
                },
            )
        props = {"name": name, "from_bus": from_b, "to_bus": to_b}
        if sw.get("status") is not None:
            props["status"] = str(sw["status"])
        if sw.get("rated_a") is not None:
            props["rated_a"] = float(sw["rated_a"])
        elements.append(
            EtapElement(
                element_type="switch",
                name=name,
                properties=props,
            )
        )
    return elements


def _build_branch_and_load_elements(
    lines: list[dict[str, Any]],
    cables: list[dict[str, Any]],
    loads: list[dict[str, Any]],
    generators: list[dict[str, Any]],
    motors: list[dict[str, Any]],
    capacitors: list[dict[str, Any]],
    reactors: list[dict[str, Any]],
    relays: list[dict[str, Any]],
    allow_incomplete: bool = False,
) -> list[EtapElement]:
    elements: list[EtapElement] = []

    for line in lines:
        name = str(line.get("name") or line.get("id") or "LINE")
        from_b = str(line.get("from_bus") or "").strip()
        to_b = str(line.get("to_bus") or "").strip()
        r_val = line.get("r_pu") if line.get("r_pu") is not None else line.get("r1")
        x_val = line.get("x_pu") if line.get("x_pu") is not None else line.get("x1")
        mva_val = (
            line.get("rating_mva") if line.get("rating_mva") is not None else line.get("rating")
        )

        if not allow_incomplete:
            missing = []
            if not from_b:
                missing.append("from_bus")
            if not to_b:
                missing.append("to_bus")
            if r_val is None:
                missing.append("r_pu")
            if x_val is None:
                missing.append("x_pu")
            if mva_val is None:
                missing.append("rating_mva")
            if missing:
                raise ETAPRestError(
                    "INCOMPLETE_DATA",
                    f"Line '{name}' is missing mandatory electrical parameters: {missing}",
                    {"element": name, "missing": missing},
                )

        props: dict[str, Any] = {
            "name": name,
            "from_bus": from_b,
            "to_bus": to_b,
            "r_pu": float(r_val) if r_val is not None else None,
            "x_pu": float(x_val) if x_val is not None else None,
            "rating_mva": float(mva_val) if mva_val is not None else None,
        }
        for opt_key in ("b_pu", "length_km", "rating_a"):
            if line.get(opt_key) is not None:
                try:
                    props[opt_key] = float(line[opt_key])
                except (ValueError, TypeError):
                    props[opt_key] = line[opt_key]

        elements.append(
            EtapElement(
                element_type="line",
                name=name,
                properties=props,
            )
        )

    for cable in cables:
        name = str(cable.get("name") or cable.get("id") or "CBL")
        from_b = str(cable.get("from_bus") or "").strip()
        to_b = str(cable.get("to_bus") or "").strip()
        if (not from_b or not to_b) and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Cable '{name}' is missing mandatory terminal buses",
                {
                    "element": name,
                    "missing": [f for f, v in [("from_bus", from_b), ("to_bus", to_b)] if not v],
                },
            )
        props = {
            "name": name,
            "from_bus": from_b,
            "to_bus": to_b,
        }
        for opt_key in ("r_pu", "x_pu", "b_pu", "length_km", "rating_a", "conductor_material"):
            if cable.get(opt_key) is not None:
                val = cable[opt_key]
                if opt_key in ("r_pu", "x_pu", "b_pu", "length_km", "rating_a"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[opt_key] = val
        elements.append(
            EtapElement(
                element_type="cable",
                name=name,
                properties=props,
            )
        )

    for ld in loads:
        name = str(ld.get("name") or ld.get("id") or "LOAD")
        bus = str(ld.get("bus") or "").strip()
        if not bus and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Load '{name}' is missing mandatory field 'bus'",
                {"element": name, "missing": ["bus"]},
            )
        props = {"name": name, "bus": bus}
        for opt_key in ("p_mw", "q_mvar", "model", "load_model", "status"):
            if ld.get(opt_key) is not None:
                val = ld[opt_key]
                if opt_key in ("p_mw", "q_mvar"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[opt_key] = val
        elements.append(
            EtapElement(
                element_type="load",
                name=name,
                properties=props,
            )
        )

    for gen in generators:
        name = str(gen.get("name") or gen.get("id") or "GEN")
        bus = str(gen.get("bus") or "").strip()
        if not bus and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Generator '{name}' is missing mandatory field 'bus'",
                {"element": name, "missing": ["bus"]},
            )
        props = {"name": name, "bus": bus}
        for opt_key in ("rating_mva", "p_mw", "q_mvar", "v_setpoint", "q_min", "q_max", "status"):
            if gen.get(opt_key) is not None:
                val = gen[opt_key]
                if opt_key in ("rating_mva", "p_mw", "q_mvar", "v_setpoint", "q_min", "q_max"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[opt_key] = val
        elements.append(
            EtapElement(
                element_type="generator",
                name=name,
                properties=props,
            )
        )

    for mtr in motors:
        name = str(mtr.get("name") or mtr.get("id") or "MTR")
        bus = str(mtr.get("bus") or "").strip()
        if not bus and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Motor '{name}' is missing mandatory field 'bus'",
                {"element": name, "missing": ["bus"]},
            )
        props = {"name": name, "bus": bus}
        for opt_key in ("rated_kw", "rated_kv", "pf", "efficiency", "status"):
            if mtr.get(opt_key) is not None:
                val = mtr[opt_key]
                if opt_key in ("rated_kw", "rated_kv", "pf", "efficiency"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[opt_key] = val
        elements.append(
            EtapElement(
                element_type="motor",
                name=name,
                properties=props,
            )
        )

    for cap in capacitors:
        name = str(cap.get("name") or cap.get("id") or "CAP")
        bus = str(cap.get("bus") or "").strip()
        if not bus and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Capacitor '{name}' is missing mandatory field 'bus'",
                {"element": name, "missing": ["bus"]},
            )
        props = {"name": name, "bus": bus}
        for opt_key in ("q_mvar", "rated_kv", "status"):
            if cap.get(opt_key) is not None:
                val = cap[opt_key]
                if opt_key in ("q_mvar", "rated_kv"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[opt_key] = val
        elements.append(
            EtapElement(
                element_type="capacitor",
                name=name,
                properties=props,
            )
        )

    for rc in reactors:
        name = str(rc.get("name") or rc.get("id") or "REACT")
        from_b = str(rc.get("from_bus") or "").strip()
        to_b = str(rc.get("to_bus") or "").strip()
        if (not from_b or not to_b) and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Reactor '{name}' is missing mandatory terminal buses",
                {
                    "element": name,
                    "missing": [f for f, v in [("from_bus", from_b), ("to_bus", to_b)] if not v],
                },
            )
        props = {"name": name, "from_bus": from_b, "to_bus": to_b}
        for opt_key in ("x_pu", "rating_mva", "status"):
            if rc.get(opt_key) is not None:
                val = rc[opt_key]
                if opt_key in ("x_pu", "rating_mva"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[opt_key] = val
        elements.append(
            EtapElement(
                element_type="reactor",
                name=name,
                properties=props,
            )
        )

    for rly in relays:
        name = str(rly.get("name") or rly.get("id") or "RLY")
        bus = str(rly.get("bus") or "").strip()
        if not bus and not allow_incomplete:
            raise ETAPRestError(
                "INCOMPLETE_DATA",
                f"Relay '{name}' is missing mandatory field 'bus'",
                {"element": name, "missing": ["bus"]},
            )
        props = {"name": name, "bus": bus}
        for opt_key in ("protected_element", "curve_type", "time_dial", "pickup_a"):
            if rly.get(opt_key) is not None:
                val = rly[opt_key]
                if opt_key in ("time_dial", "pickup_a"):
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                props[opt_key] = val
        elements.append(
            EtapElement(
                element_type="relay",
                name=name,
                properties=props,
            )
        )

    return elements
