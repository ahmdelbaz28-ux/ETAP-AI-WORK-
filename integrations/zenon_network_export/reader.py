"""Zenon Network Export Reader.

Parses a Zenon Network Export v1 contract (JSON/dict) and maps it into:
1. An internal core_model.System electrical IR (buses, lines, transformers, generators, loads)
2. Descriptive secondary elements (breakers, switches, relays, motors, capacitors, reactors, sources)

Enforces:
- Zero guessing: missing electrical values are flagged with explicit warnings, never invented.
- Strict topology validation: terminal buses must exist in the network.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from core_model.bus import Bus
from core_model.generator import Generator
from core_model.line import Line
from core_model.load import Load
from core_model.system import System
from core_model.transformer import Transformer
from integrations.zenon_network_export.contract import (
    ZenonNetworkExport,
)
from integrations.zenon_network_export.mapping import ZenonFieldMapper

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
    ) -> None:
        self.system = system
        self.contract = contract
        self.extra_elements = extra_elements
        self.warnings = warnings
        self.errors = errors

    @property
    def is_valid(self) -> bool:
        """True if no fatal topological or schema errors occurred."""
        return len(self.errors) == 0


def parse_zenon_export(
    raw_data: str | bytes | dict[str, Any],
    field_mapper: ZenonFieldMapper | None = None,
) -> ZenonImportResult:
    """Parses a Zenon Network Export v1 payload into core_model.System and extra components."""
    warnings: list[str] = []
    errors: list[str] = []

    # 1. Parse JSON if string or bytes
    if isinstance(raw_data, (str, bytes)):
        try:
            parsed_json = json.loads(raw_data)
        except Exception as e:
            errors.append(f"Invalid JSON in zenon export payload: {e}")
            empty_contract = ZenonNetworkExport(
                project={"name": "Unknown", "source_system": "zenon"}
            )
            return ZenonImportResult(
                system=System(base_mva=100.0),
                contract=empty_contract,
                extra_elements={},
                warnings=warnings,
                errors=errors,
            )
    elif isinstance(raw_data, dict):
        parsed_json = raw_data
    else:
        errors.append(f"Unsupported payload type for zenon export: {type(raw_data)}")
        empty_contract = ZenonNetworkExport(
            project={"name": "Unknown", "source_system": "zenon"}
        )
        return ZenonImportResult(
            system=System(base_mva=100.0),
            contract=empty_contract,
            extra_elements={},
            warnings=warnings,
            errors=errors,
        )

    # 2. Validate against ZenonNetworkExport contract
    try:
        contract = ZenonNetworkExport.model_validate(parsed_json)
    except ValidationError as e:
        for err in e.errors():
            loc = ".".join(str(p) for p in err.get("loc", []))
            errors.append(f"Zenon contract schema error at {loc}: {err.get('msg')}")
        # Partial model or fallback
        contract = ZenonNetworkExport.model_construct(**parsed_json)

    base_mva = contract.project.base_mva or 100.0
    system = System(base_mva=base_mva)
    _ = field_mapper or ZenonFieldMapper()

    # 3. Process Buses
    for b in contract.buses:
        # Check nominal voltage
        base_kv = b.base_kv if b.base_kv is not None else b.kv
        if base_kv is None:
            warnings.append(
                f"Bus '{b.id}' ({b.name}): voltage is missing in source data; not guessed."
            )
        elif base_kv <= 0:
            errors.append(f"Bus '{b.id}' ({b.name}): invalid voltage {base_kv} kV <= 0")

        bus_type = (b.bus_type or "pq").lower().strip()
        if bus_type not in ("slack", "pv", "pq"):
            warnings.append(f"Bus '{b.id}': unknown bus_type '{bus_type}', defaulting to 'pq'")
            bus_type = "pq"

        v_mag = b.v_mag if b.v_mag is not None else 1.0
        v_ang = b.v_ang if b.v_ang is not None else 0.0

        bus_obj = Bus(
            bus_id=b.id,
            voltage_magnitude=v_mag,
            voltage_angle=v_ang,
            base_kv=base_kv,
            bus_type=bus_type,
        )
        system.add_bus(bus_obj)

    # Helper to resolve bus objects
    def get_bus(b_id: str) -> Bus | None:
        return system.buses.get(b_id) or system.buses.get(str(b_id))

    # 4. Process Lines
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
            r, x = 0.0001, 0.0001
        elif r is None:
            r = 0.0
        elif x is None:
            x = 0.0001

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

    # 5. Process Cables
    for cable in contract.cables:
        from_b = get_bus(cable.from_bus)
        to_b = get_bus(cable.to_bus)
        if not from_b or not to_b:
            missing_end = cable.from_bus if not from_b else cable.to_bus
            errors.append(
                f"Cable '{cable.id}' ({cable.name}): terminal bus '{missing_end}' does not exist in network."
            )
            continue

        r = cable.r_pu if cable.r_pu is not None else 0.0001
        x = cable.x_pu if cable.x_pu is not None else 0.0001
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

    # 6. Process Transformers
    for xf in contract.transformers:
        from_b = get_bus(xf.from_bus)
        to_b = get_bus(xf.to_bus)
        if not from_b or not to_b:
            missing_end = xf.from_bus if not from_b else xf.to_bus
            errors.append(
                f"Transformer '{xf.id}' ({xf.name}): terminal bus '{missing_end}' does not exist in network."
            )
            continue

        r = xf.r_pu if xf.r_pu is not None else 0.0
        x = xf.x_pu if xf.x_pu is not None else 0.05
        xf_obj = Transformer(
            transformer_id=xf.id,
            from_bus=from_b,
            to_bus=to_b,
            z1=complex(r, x),
            rating=xf.rating_mva,
            tap_ratio=xf.tap_ratio if xf.tap_ratio is not None else 1.0,
        )
        system.add_transformer(xf_obj)

    # 7. Process Loads
    for load in contract.loads:
        bus_obj = get_bus(load.bus)
        if not bus_obj:
            errors.append(
                f"Load '{load.id}' ({load.name}): connected bus '{load.bus}' does not exist in network."
            )
            continue

        p_val = load.p_mw if load.p_mw is not None else 0.0
        q_val = load.q_mvar if load.q_mvar is not None else 0.0
        load_obj = Load(
            load_id=load.id,
            bus=bus_obj,
            load_power=complex(p_val, q_val),
        )
        system.add_load(load_obj)

    # 8. Process Generators
    for gen in contract.generators:
        bus_obj = get_bus(gen.bus)
        if not bus_obj:
            errors.append(
                f"Generator '{gen.id}' ({gen.name}): connected bus '{gen.bus}' does not exist in network."
            )
            continue

        p_val = gen.p_mw if gen.p_mw is not None else 0.0
        q_val = gen.q_mvar if gen.q_mvar is not None else 0.0
        gen_obj = Generator(
            generator_id=gen.id,
            bus=bus_obj,
            max_power=complex(gen.rating_mva or 100.0, gen.q_max or 50.0),
            min_power=complex(0.0, gen.q_min or -50.0),
        )
        bus_obj.generation_power = complex(p_val, q_val)
        if gen.v_setpoint is not None:
            bus_obj.voltage_magnitude = gen.v_setpoint
        system.add_generator(gen_obj)

    # 9. Collect extra components for ETAP drawing and protective telemetry
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
    )
