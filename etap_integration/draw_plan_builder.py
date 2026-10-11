"""ETAP Draw Plan Builder.

Builds bounded, dependency-ordered EtapDrawPlan chunks from internal models
(core_model.System or dictionaries from sync_engine.export_to_etap) and provides
atomic multi-chunk execution with automatic rollback on failure.

Rules:
- Strict Dependency Ordering:
  buses -> transformers -> breakers/switches -> lines/cables/loads/generators
- Zero Geometry:
  Coordinates and position parameters are strictly forbidden. Layout is left to ETAP Auto-Build.
- Pre-flight Validation:
  Every terminal bus (from_bus, to_bus, bus) must exist in the network chunks or project.
- Atomic Multi-Chunk Rollback:
  If chunk N fails, all elements created in chunks 1..(N-1) are deleted immediately.
"""

from __future__ import annotations

import logging
from typing import Any

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
    model: System | dict[str, Any] | Any,
    project_id: str,
    max_items: int = MAX_ELEMENTS_PER_REQUEST,
    extra_known_buses: set[str] | None = None,
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
    components = _normalize_model_components(model)

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
    bus_elements = _build_bus_elements(components["buses"])
    xf_elements = _build_transformer_elements(components["transformers"])
    switchgear_elements = _build_switchgear_elements(
        components.get("breakers", []), components.get("switches", [])
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
        ordered_elements[i : i + chunk_size]
        for i in range(0, len(ordered_elements), chunk_size)
    ]

    total_chunks = len(chunks)
    plans: list[EtapDrawPlan] = []
    for idx, chunk in enumerate(chunks):
        plan = EtapDrawPlan(
            project_id=project_id,
            items=chunk,
            delete_ids=[],
            reason=f"Draw network chunk {idx + 1}/{total_chunks} for project {project_id}",
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


def _normalize_model_components(model: Any) -> dict[str, list[dict[str, Any]]]:
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
            components["buses"].append(
                {
                    "id": str(bid),
                    "name": str(b.bus_id),
                    "base_kv": b.base_kv or 11.0,
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
                }
            )
        for ln in model.lines:
            components["lines"].append(
                {
                    "id": str(ln.line_id),
                    "name": f"LINE_{ln.line_id}",
                    "from_bus": str(ln.from_bus.bus_id),
                    "to_bus": str(ln.to_bus.bus_id),
                    "r_pu": ln.z1.real,
                    "x_pu": ln.z1.imag,
                    "rating_mva": getattr(ln, "rating", None) or 100.0,
                }
            )
        for ld in model.loads:
            components["loads"].append(
                {
                    "id": str(ld.load_id),
                    "name": f"LOAD_{ld.load_id}",
                    "bus": str(ld.bus.bus_id),
                    "p_mw": ld.load_power.real * model.base_mva,
                    "q_mvar": ld.load_power.imag * model.base_mva,
                }
            )
        for gen in model.generators:
            components["generators"].append(
                {
                    "id": str(gen.generator_id),
                    "name": f"GEN_{gen.generator_id}",
                    "bus": str(gen.bus.bus_id),
                }
            )
        return components

    if isinstance(model, dict):
        # Could be {objects: {...}} or direct {buses: [...], ...}
        src = model.get("objects", model)
        for k in components:
            if k in src and isinstance(src[k], list):
                components[k].extend(src[k])

        # Also pull from extra_elements if present
        extra = model.get("extra_elements", {})
        if isinstance(extra, dict):
            for k in components:
                if k in extra and isinstance(extra[k], list):
                    components[k].extend(extra[k])
        return components

    raise ETAPRestError(
        "INVALID_MODEL",
        f"Unsupported model type for ETAP draw plan: {type(model)}",
    )


def _validate_connectivity(
    components: dict[str, list[dict[str, Any]]],
    known_buses: set[str],
) -> None:
    """Ensures every element's terminal buses exist in the model or target project."""
    for xf in components.get("transformers", []):
        _assert_bus_exists(xf.get("from_bus"), "transformer", xf.get("name", xf.get("id")), known_buses)
        _assert_bus_exists(xf.get("to_bus"), "transformer", xf.get("name", xf.get("id")), known_buses)

    for brk in components.get("breakers", []):
        b = brk.get("from_bus") or brk.get("bus")
        _assert_bus_exists(b, "breaker", brk.get("name", brk.get("id")), known_buses)

    for sw in components.get("switches", []):
        b = sw.get("from_bus") or sw.get("bus")
        _assert_bus_exists(b, "switch", sw.get("name", sw.get("id")), known_buses)

    for line in components.get("lines", []):
        _assert_bus_exists(line.get("from_bus"), "line", line.get("name", line.get("id")), known_buses)
        _assert_bus_exists(line.get("to_bus"), "line", line.get("name", line.get("id")), known_buses)

    for cable in components.get("cables", []):
        _assert_bus_exists(cable.get("from_bus"), "cable", cable.get("name", cable.get("id")), known_buses)
        _assert_bus_exists(cable.get("to_bus"), "cable", cable.get("name", cable.get("id")), known_buses)

    for ld in components.get("loads", []):
        _assert_bus_exists(ld.get("bus"), "load", ld.get("name", ld.get("id")), known_buses)

    for gen in components.get("generators", []):
        _assert_bus_exists(gen.get("bus"), "generator", gen.get("name", gen.get("id")), known_buses)

    for mtr in components.get("motors", []):
        _assert_bus_exists(mtr.get("bus"), "motor", mtr.get("name", mtr.get("id")), known_buses)

    for cap in components.get("capacitors", []):
        _assert_bus_exists(cap.get("bus"), "capacitor", cap.get("name", cap.get("id")), known_buses)

    for rly in components.get("relays", []):
        _assert_bus_exists(rly.get("bus"), "relay", rly.get("name", rly.get("id")), known_buses)


def _assert_bus_exists(
    bus_ref: Any,
    elem_type: str,
    elem_name: Any,
    known_buses: set[str],
) -> None:
    if not bus_ref or str(bus_ref).strip() not in known_buses:
        raise ETAPRestError(
            "INVALID_TOPOLOGY",
            f"Element '{elem_name}' ({elem_type}) references non-existent bus '{bus_ref}'.",
            {"element": str(elem_name), "element_type": elem_type, "missing_bus": str(bus_ref)},
        )


# ---------------------------------------------------------------------------
# Element Construction Helpers
# ---------------------------------------------------------------------------


def _build_bus_elements(buses: list[dict[str, Any]]) -> list[EtapElement]:
    elements: list[EtapElement] = []
    for b in buses:
        name = str(b.get("name") or b.get("id") or "BUS")
        kv = float(b.get("base_kv") or b.get("voltage_kv") or 11.0)
        elements.append(
            EtapElement(
                element_type="bus",
                name=name,
                properties={"name": name, "base_kv": kv},
            )
        )
    return elements


def _build_transformer_elements(transformers: list[dict[str, Any]]) -> list[EtapElement]:
    elements: list[EtapElement] = []
    for xf in transformers:
        name = str(xf.get("name") or xf.get("id") or "XF")
        props: dict[str, Any] = {
            "name": name,
            "from_bus": str(xf["from_bus"]),
            "to_bus": str(xf["to_bus"]),
        }
        if xf.get("rating_mva") is not None:
            props["rating_mva"] = float(xf["rating_mva"])
        elements.append(
            EtapElement(
                element_type="transformer",
                name=name,
                properties=props,
            )
        )
    return elements


def _build_switchgear_elements(
    breakers: list[dict[str, Any]], switches: list[dict[str, Any]]
) -> list[EtapElement]:
    elements: list[EtapElement] = []
    for brk in breakers:
        name = str(brk.get("name") or brk.get("id") or "CB")
        from_b = str(brk.get("from_bus") or brk.get("bus") or "")
        to_b = str(brk.get("to_bus") or brk.get("bus") or from_b)
        elements.append(
            EtapElement(
                element_type="breaker",
                name=name,
                properties={"name": name, "from_bus": from_b, "to_bus": to_b},
            )
        )
    for sw in switches:
        name = str(sw.get("name") or sw.get("id") or "SW")
        from_b = str(sw.get("from_bus") or sw.get("bus") or "")
        to_b = str(sw.get("to_bus") or sw.get("bus") or from_b)
        elements.append(
            EtapElement(
                element_type="switch",
                name=name,
                properties={"name": name, "from_bus": from_b, "to_bus": to_b},
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
) -> list[EtapElement]:
    elements: list[EtapElement] = []

    for line in lines:
        name = str(line.get("name") or line.get("id") or "LINE")
        r_val = float(line.get("r_pu") if line.get("r_pu") is not None else (line.get("r1") or 0.001))
        x_val = float(line.get("x_pu") if line.get("x_pu") is not None else (line.get("x1") or 0.005))
        mva_val = float(line.get("rating_mva") if line.get("rating_mva") is not None else (line.get("rating") or 100.0))
        elements.append(
            EtapElement(
                element_type="line",
                name=name,
                properties={
                    "name": name,
                    "from_bus": str(line["from_bus"]),
                    "to_bus": str(line["to_bus"]),
                    "r_pu": r_val,
                    "x_pu": x_val,
                    "rating_mva": mva_val,
                },
            )
        )

    for cable in cables:
        name = str(cable.get("name") or cable.get("id") or "CBL")
        elements.append(
            EtapElement(
                element_type="cable",
                name=name,
                properties={
                    "name": name,
                    "from_bus": str(cable["from_bus"]),
                    "to_bus": str(cable["to_bus"]),
                },
            )
        )

    for ld in loads:
        name = str(ld.get("name") or ld.get("id") or "LOAD")
        elements.append(
            EtapElement(
                element_type="load",
                name=name,
                properties={"name": name, "bus": str(ld["bus"])},
            )
        )

    for gen in generators:
        name = str(gen.get("name") or gen.get("id") or "GEN")
        elements.append(
            EtapElement(
                element_type="generator",
                name=name,
                properties={"name": name, "bus": str(gen["bus"])},
            )
        )

    for mtr in motors:
        name = str(mtr.get("name") or mtr.get("id") or "MTR")
        elements.append(
            EtapElement(
                element_type="motor",
                name=name,
                properties={"name": name, "bus": str(mtr["bus"])},
            )
        )

    for cap in capacitors:
        name = str(cap.get("name") or cap.get("id") or "CAP")
        elements.append(
            EtapElement(
                element_type="capacitor",
                name=name,
                properties={"name": name, "bus": str(cap["bus"])},
            )
        )

    for rc in reactors:
        name = str(rc.get("name") or rc.get("id") or "REACT")
        from_b = str(rc.get("from_bus") or rc.get("bus") or "")
        to_b = str(rc.get("to_bus") or rc.get("bus") or from_b)
        elements.append(
            EtapElement(
                element_type="reactor",
                name=name,
                properties={"name": name, "from_bus": from_b, "to_bus": to_b},
            )
        )

    for rly in relays:
        name = str(rly.get("name") or rly.get("id") or "RLY")
        elements.append(
            EtapElement(
                element_type="relay",
                name=name,
                properties={"name": name, "bus": str(rly["bus"])},
            )
        )

    return elements
