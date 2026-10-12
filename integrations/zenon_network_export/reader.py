"""Zenon Network Export Reader.

Parses a Zenon Network Export v1 contract or raw dump (JSON/dict) and maps it into:
1. An internal core_model.System electrical IR (buses, lines, transformers, generators, loads)
2. Descriptive secondary elements (breakers, switches, relays, motors, capacitors, reactors, sources)

Enforces:
- Zero guessing: missing electrical values are flagged with explicit warnings and tracked in incomplete, never invented.
- Strict topology validation: terminal buses must exist in the network.
- Slack conversion: Sources are converted into slack infeed generators.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import ValidationError

from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from core_model.transformer import Transformer
from integrations.zenon_network_export.classifier import ClassifyResult, ZenonClassifier
from integrations.zenon_network_export.contract import (
    ZenonNetworkExport,
    ZenonProjectMetadata,
)
from integrations.zenon_network_export.mapping import ZenonFieldMapper
from integrations.zenon_network_export.raw_dump import ZenonRawDump

logger = logging.getLogger(__name__)


class ZenonImportResult:
    """Result of parsing and transforming a Zenon network export."""

    def __init__(
        self,
        system: System,
        contract: ZenonNetworkExport,
        extra_elements: dict[str, list[dict[str, Any]]],
        warnings: list[str],
        errors: list[str],
        incomplete: list[dict[str, Any]] | None = None,
        classify_result: ClassifyResult | None = None,
    ) -> None:
        self.system = system
        self.contract = contract
        self.extra_elements = extra_elements
        self.warnings = warnings
        self.errors = errors
        self.incomplete = incomplete or []
        self.classify_result = classify_result

    @property
    def is_valid(self) -> bool:
        """True if no fatal topological or schema errors occurred."""
        return len(self.errors) == 0


def parse_zenon_export(
    raw_data: str | bytes | dict[str, Any],
    field_mapper: ZenonFieldMapper | None = None,
) -> ZenonImportResult:
    """Parses a Zenon Network Export v1 payload or raw dump into core_model.System and extra components."""
    warnings: list[str] = []
    errors: list[str] = []
    incomplete: list[dict[str, Any]] = []
    classify_res: Optional[ClassifyResult] = None

    mapper = field_mapper or ZenonFieldMapper()

    # 1. Parse JSON if string or bytes
    if isinstance(raw_data, (str, bytes)):
        try:
            parsed_json = json.loads(raw_data)
        except Exception as e:
            errors.append(f"Invalid JSON in zenon export payload: {e}")
            empty_contract = ZenonNetworkExport(
                project=ZenonProjectMetadata(name="Unknown", source_system="zenon")
            )
            return ZenonImportResult(
                system=System(base_mva=None),
                contract=empty_contract,
                extra_elements={},
                warnings=warnings,
                errors=errors,
                incomplete=incomplete,
            )
    elif isinstance(raw_data, dict):
        parsed_json = raw_data
    else:
        errors.append(f"Unsupported payload type for zenon export: {type(raw_data)}")
        empty_contract = ZenonNetworkExport(
            project=ZenonProjectMetadata(name="Unknown", source_system="zenon")
        )
        return ZenonImportResult(
            system=System(base_mva=None),
            contract=empty_contract,
            extra_elements={},
            warnings=warnings,
            errors=errors,
            incomplete=incomplete,
        )

    # 2. Detect format: ZenonRawDump vs. ZenonNetworkExport contract
    is_raw_dump = False
    if isinstance(parsed_json, dict):
        if ("variables" in parsed_json or parsed_json.get("dump_version")) and "buses" not in parsed_json:
            is_raw_dump = True

    if is_raw_dump:
        try:
            raw_dump_model = ZenonRawDump.model_validate(parsed_json)
            classifier = ZenonClassifier(field_mapper=mapper)
            classify_res = classifier.classify_raw_dump(raw_dump_model)
            contract = classify_res.contract
            warnings.extend(classify_res.warnings)
            errors.extend(classify_res.errors)
            incomplete.extend(classify_res.incomplete)
        except Exception as e:
            errors.append(f"Zenon raw dump schema/classification error: {e}")
            contract = ZenonNetworkExport(
                project=ZenonProjectMetadata(name="Unknown", source_system="zenon")
            )
    else:
        # Validate against standard ZenonNetworkExport contract
        try:
            contract = ZenonNetworkExport.model_validate(parsed_json)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(p) for p in err.get("loc", []))
                errors.append(f"Zenon contract schema error at {loc}: {err.get('msg')}")
            contract = ZenonNetworkExport.model_construct(**parsed_json)

    # 3. Base MVA validation (no synthetic fallback)
    base_mva = contract.project.base_mva
    if base_mva is None:
        warnings.append(
            f"Project '{contract.project.name}': base_mva is missing in source data; not guessed."
        )
        incomplete.append({
            "element": "project",
            "field": "base_mva",
            "reason": "missing_base_mva",
        })

    system = System(base_mva=base_mva)

    # 4. Process Buses
    for b in contract.buses:
        base_kv = b.base_kv if b.base_kv is not None else b.kv
        if base_kv is None:
            warnings.append(
                f"Bus '{b.id}' ({b.name}): voltage is missing in source data; not guessed."
            )
            incomplete.append({
                "element": f"bus:{b.id}",
                "field": "base_kv",
                "reason": "missing_voltage",
            })
        elif base_kv <= 0:
            errors.append(f"Bus '{b.id}' ({b.name}): invalid voltage {base_kv} kV <= 0")

        bus_type = (b.bus_type or "pq").lower().strip()
        if bus_type not in ("slack", "pv", "pq"):
            warnings.append(f"Bus '{b.id}': unknown bus_type '{bus_type}', defaulting to 'pq'")
            bus_type = "pq"

        v_mag = b.v_mag if b.v_mag is not None else 1.0
        v_ang = b.v_ang
        if v_ang is None:
            warnings.append(
                f"Bus '{b.id}' ({b.name}): voltage angle v_ang is missing in source data; not guessed."
            )
            incomplete.append({
                "element": f"bus:{b.id}",
                "field": "v_ang",
                "reason": "missing_voltage_angle",
            })

        bus_obj = Bus(
            bus_id=b.id,
            voltage_magnitude=v_mag,
            voltage_angle=v_ang,
            base_kv=base_kv,
            bus_type=bus_type,
        )
        system.add_bus(bus_obj)

    def get_bus(b_id: str) -> Bus | None:
        return system.buses.get(b_id) or system.buses.get(str(b_id))

    # 5. Process Lines (strictly reject missing impedance)
    for line in contract.lines:
        from_b = get_bus(line.from_bus)
        to_b = get_bus(line.to_bus)
        if not from_b or not to_b:
            missing_end = line.from_bus if not from_b else line.to_bus
            errors.append(
                f"Line '{line.id}' ({line.name}): terminal bus '{missing_end}' does not exist in network."
            )
            continue

        r = line.r_pu
        x = line.x_pu
        if r is None and x is None:
            warnings.append(
                f"Line '{line.id}' ({line.name}): impedance r_pu/x_pu missing in source data; not guessed."
            )
            incomplete.append({
                "element": f"line:{line.id}",
                "field": "impedance",
                "reason": "missing_line_impedance",
            })
            continue
        elif r is None:
            warnings.append(f"Line '{line.id}' ({line.name}): r_pu missing in source data; not guessed.")
            incomplete.append({
                "element": f"line:{line.id}",
                "field": "r_pu",
                "reason": "missing_r_pu",
            })
            continue
        elif x is None:
            warnings.append(f"Line '{line.id}' ({line.name}): x_pu missing in source data; not guessed.")
            incomplete.append({
                "element": f"line:{line.id}",
                "field": "x_pu",
                "reason": "missing_x_pu",
            })
            continue

        b_shunt = line.b_pu if line.b_pu is not None else 0.0
        line_obj = Line(
            line_id=line.id,
            from_bus=from_b,
            to_bus=to_b,
            z1=complex(r, x),
            yshunt1=complex(0.0, b_shunt),
            rating=line.rating_mva,
        )
        system.add_line(line_obj)

    # 6. Process Cables (strictly reject missing impedance)
    for cable in contract.cables:
        from_b = get_bus(cable.from_bus)
        to_b = get_bus(cable.to_bus)
        if not from_b or not to_b:
            missing_end = cable.from_bus if not from_b else cable.to_bus
            errors.append(
                f"Cable '{cable.id}' ({cable.name}): terminal bus '{missing_end}' does not exist in network."
            )
            continue

        r = cable.r_pu
        x = cable.x_pu
        if r is None or x is None:
            warnings.append(
                f"Cable '{cable.id}' ({cable.name}): impedance r_pu/x_pu missing in source data; not guessed."
            )
            incomplete.append({
                "element": f"cable:{cable.id}",
                "field": "impedance",
                "reason": "missing_cable_impedance",
            })
            continue

        b_shunt = cable.b_pu if cable.b_pu is not None else 0.0
        cable_obj = Line(
            line_id=cable.id,
            from_bus=from_b,
            to_bus=to_b,
            z1=complex(r, x),
            yshunt1=complex(0.0, b_shunt),
            rating=cable.rating_a,
        )
        system.add_line(cable_obj)

    # 7. Process Transformers (strictly reject missing impedance)
    for xf in contract.transformers:
        from_b = get_bus(xf.from_bus)
        to_b = get_bus(xf.to_bus)
        if not from_b or not to_b:
            missing_end = xf.from_bus if not from_b else xf.to_bus
            errors.append(
                f"Transformer '{xf.id}' ({xf.name}): terminal bus '{missing_end}' does not exist in network."
            )
            continue

        r = xf.r_pu
        x = xf.x_pu
        if r is None or x is None:
            warnings.append(
                f"Transformer '{xf.id}' ({xf.name}): impedance r_pu/x_pu missing in source data; not guessed."
            )
            incomplete.append({
                "element": f"transformer:{xf.id}",
                "field": "impedance",
                "reason": "missing_transformer_impedance",
            })
            continue

        xf_obj = Transformer(
            transformer_id=xf.id,
            from_bus=from_b,
            to_bus=to_b,
            z1=complex(r, x),
            rating=xf.rating_mva,
            tap_ratio=xf.tap_ratio if xf.tap_ratio is not None else 1.0,
        )
        system.add_transformer(xf_obj)

    # 8. Process Loads (strictly reject missing power)
    for load in contract.loads:
        bus_obj = get_bus(load.bus)
        if not bus_obj:
            errors.append(
                f"Load '{load.id}' ({load.name}): connected bus '{load.bus}' does not exist in network."
            )
            continue

        p_val = load.p_mw
        q_val = load.q_mvar
        if p_val is None or q_val is None:
            warnings.append(
                f"Load '{load.id}' ({load.name}): active/reactive power p_mw/q_mvar missing in source data; not guessed."
            )
            incomplete.append({
                "element": f"load:{load.id}",
                "field": "power",
                "reason": "missing_load_power",
            })
            continue

        load_obj = Load(
            load_id=load.id,
            bus=bus_obj,
            load_power=complex(p_val, q_val),
        )
        system.add_load(load_obj)

    # 9. Process Generators (strictly reject missing power/rating)
    for gen in contract.generators:
        bus_obj = get_bus(gen.bus)
        if not bus_obj:
            errors.append(
                f"Generator '{gen.id}' ({gen.name}): connected bus '{gen.bus}' does not exist in network."
            )
            continue

        p_val = gen.p_mw
        q_val = gen.q_mvar
        if p_val is None or q_val is None or gen.rating_mva is None:
            warnings.append(
                f"Generator '{gen.id}' ({gen.name}): power/rating missing in source data; not guessed."
            )
            incomplete.append({
                "element": f"generator:{gen.id}",
                "field": "power_or_rating",
                "reason": "missing_generator_rating",
            })
            continue

        q_max = gen.q_max if gen.q_max is not None else 0.0
        q_min = gen.q_min if gen.q_min is not None else 0.0
        gen_obj = Generator(
            generator_id=gen.id,
            bus=bus_obj,
            max_power=complex(gen.rating_mva, q_max),
            min_power=complex(0.0, q_min),
        )
        bus_obj.generation_power = complex(p_val, q_val)
        if gen.v_setpoint is not None:
            bus_obj.voltage_magnitude = gen.v_setpoint
        system.add_generator(gen_obj)

    # 10. Process Sources (grid infeed / slack bus generator)
    if not contract.sources:
        warnings.append(
            "No source elements (ZenonSource) found in network export; slack bus not defined."
        )
    else:
        for src in contract.sources:
            if not src.bus:
                errors.append(f"Source '{src.id}' ({src.name}): bus connection is missing.")
                continue

            bus_obj = get_bus(src.bus)
            if not bus_obj:
                errors.append(
                    f"Source '{src.id}' ({src.name}): connected bus '{src.bus}' does not exist in network."
                )
                continue

            # Mark connected bus as slack
            bus_obj.bus_type = "slack"
            if src.base_kv is not None and bus_obj.base_kv is None:
                bus_obj.base_kv = src.base_kv

            # Derive generator capacity from short circuit MVA and R/X ratio
            if src.s_sc_mva is not None:
                p_max = float(src.s_sc_mva)
                rx = float(src.rx_ratio) if src.rx_ratio is not None and src.rx_ratio > 0 else 1.0
                q_max = p_max / rx
                gen_source = Generator(
                    generator_id=f"SRC_GEN_{src.id}",
                    bus=bus_obj,
                    max_power=complex(p_max, q_max),
                    min_power=complex(0.0, -q_max),
                )
                system.add_generator(gen_source)
            else:
                incomplete.append({
                    "element": f"source:{src.id}",
                    "field": "s_sc_mva",
                    "reason": "missing_source_short_circuit_capacity",
                })

    # 11. Collect secondary components for ETAP drawing and protective telemetry
    extra_elements: dict[str, list[dict[str, Any]]] = {
        "breakers": [b.model_dump() for b in contract.breakers],
        "switches": [s.model_dump() for s in contract.switches],
        "motors": [m.model_dump() for m in contract.motors],
        "relays": [r.model_dump() for r in contract.relays],
        "capacitors": [c.model_dump() for c in contract.capacitors],
        "reactors": [rc.model_dump() for rc in contract.reactors],
        "sources": [src.model_dump() for src in contract.sources],
    }

    return ZenonImportResult(
        system=system,
        contract=contract,
        extra_elements=extra_elements,
        warnings=warnings,
        errors=errors,
        incomplete=incomplete,
        classify_result=classify_res,
    )
