"""
CAD Translation Engine
======================
Bidirectional translation between ETAP, AutoCAD, Revit, and the Unified Engineering Model.

Mapping Architecture:
  ETAP ↔ Unified Model ↔ AutoCAD
  Revit ↔ Unified Model ↔ AutoCAD
  ETAP ↔ Unified Model ↔ Revit
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Union

from autodesk_connector.shared.models import (
    Breaker,
    Bus,
    Cable,
    Generator,
    Load,
    Panel,
    SourceSystem,
    Transformer,
)
from compat import StrEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mapping Rules Registry
# ---------------------------------------------------------------------------


class MappingDirection(StrEnum):
    ETAP_TO_AUTOCAD = "etap_to_autocad"
    ETAP_TO_REVIT = "etap_to_revit"
    REVIT_TO_AUTOCAD = "revit_to_autocad"
    AUTOCAD_TO_REVIT = "autocad_to_revit"
    ETAP_TO_UNIFIED = "etap_to_unified"
    UNIFIED_TO_ETAP = "unified_to_etap"


# ---------------------------------------------------------------------------
# Drawing Element Definitions
# ---------------------------------------------------------------------------

ENTITY_DRAWING_RULES: dict[str, dict] = {
    "Bus": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-BUS",
            "layer": "E-BUS",
            "color": "1",
            "attributes": ["BUS_ID", "KV", "VMAG", "VANG", "TYPE"],
            "size": 10.0,
        },
        "revit": {
            "family_category": "Electrical Fixtures",
            "family_name": "Bus",
            "parameters": ["bus_id", "base_kv", "voltage_magnitude", "bus_type"],
        },
    },
    "Transformer": {
        "autocad": {
            "entity_type": "dynamic_block",
            "block_name": "ELEC-XFMR",
            "layer": "E-XFMR",
            "color": "2",
            "attributes": ["XF_ID", "MVA", "KV_PRIM", "KV_SEC", "Z_PCT", "TAP"],
            "dynamic_properties": {
                "tap_ratio": {"type": "double", "min": 0.8, "max": 1.2},
            },
            "size": 15.0,
        },
        "revit": {
            "family_category": "Electrical Equipment",  # NOSONAR — S1192: intentional repetition (audit constant)
            "family_name": "Transformer",
            "parameters": [
                "rated_power_mva",
                "primary_voltage_kv",
                "secondary_voltage_kv",
                "impedance_percent",
            ],
        },
    },
    "Cable": {
        "autocad": {
            "entity_type": "polyline",
            "layer": "E-CABLE",
            "color": "3",
            "linetype": "Dashed",
            "lineweight": "0.25mm",
        },
        "revit": {
            "family_category": "Cable Tray",
            "family_name": "Cable",
            "parameters": ["length_m", "conductor_size", "voltage_rating"],
        },
    },
    "Breaker": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-BREAKER",
            "layer": "E-BREAKER",
            "color": "4",
            "attributes": ["BRK_ID", "RATED_A", "INTERRUPT_KA", "POLES", "TYPE"],
            "size": 8.0,
        },
        "revit": {
            "family_category": "Electrical Equipment",
            "family_name": "CircuitBreaker",
            "parameters": ["rated_current_a", "interrupting_rating_ka", "poles"],
        },
    },
    "Panel": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-PANEL",
            "layer": "E-PANEL",
            "color": "5",
            "attributes": ["PANEL_ID", "TYPE", "VOLTAGE_V", "MAIN_A", "BUS_A", "PHASES"],
            "size": 12.0,
        },
        "revit": {
            "family_category": "Electrical Equipment",
            "family_name": "Panelboard",
            "parameters": ["panel_type", "voltage_nominal_v", "phase_count", "main_breaker_a"],
        },
    },
    "Load": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-LOAD",
            "layer": "E-LOAD",
            "color": "6",
            "attributes": ["LOAD_ID", "KW", "PF", "TYPE", "CATEGORY"],
            "size": 8.0,
        },
        "revit": {
            "family_category": "Electrical Fixtures",
            "family_name": "Load",
            "parameters": ["rated_power_kw", "power_factor", "load_type"],
        },
    },
    "Motor": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-MOTOR",
            "layer": "E-LOAD",
            "color": "6",
            "attributes": ["MOTOR_ID", "KW", "VOLT", "RPM", "STARTER"],
            "size": 10.0,
        },
        "revit": {
            "family_category": "Mechanical Equipment",
            "family_name": "Motor",
            "parameters": ["rated_power_kw", "rated_voltage_v", "rated_speed_rpm"],
        },
    },
    "Generator": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-GEN",
            "layer": "E-EQUIP",
            "color": "7",
            "attributes": ["GEN_ID", "MW", "MVA", "PF", "TYPE"],
            "size": 14.0,
        },
        "revit": {
            "family_category": "Electrical Equipment",
            "family_name": "Generator",
            "parameters": ["rated_power_mw", "power_factor", "generator_type"],
        },
    },
    "Switchboard": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-SWBD",
            "layer": "E-PANEL",
            "color": "5",
            "attributes": ["SWBD_ID", "VOLT", "BUS_A", "INTERRUPT_KA"],
            "size": 16.0,
        },
        "revit": {
            "family_category": "Electrical Equipment",
            "family_name": "Switchboard",
            "parameters": ["voltage_nominal_v", "bus_rating_a", "interrupting_rating_ka"],
        },
    },
    "Relay": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-RELAY",
            "layer": "E-RELAY",
            "color": "4",
            "attributes": ["RELAY_ID", "TYPE", "PICKUP", "TD", "CT_RATIO"],
            "size": 7.0,
        },
        "revit": {
            "family_category": "Electrical Equipment",
            "family_name": "Relay",
            "parameters": ["relay_type", "pickup_a", "time_dial", "ct_ratio"],
        },
    },
    "Equipment": {
        "autocad": {
            "entity_type": "block",
            "block_name": "ELEC-EQUIP",
            "layer": "E-EQUIP",
            "color": "7",
            "attributes": ["EQ_ID", "CATEGORY", "KVA", "VOLT"],
            "size": 10.0,
        },
        "revit": {
            "family_category": "Electrical Equipment",
            "family_name": "Equipment",
            "parameters": ["equipment_category", "rated_power_kva", "voltage_nominal_v"],
        },
    },
    "Conduit": {
        "autocad": {
            "entity_type": "polyline",
            "layer": "E-CONDUIT",
            "color": "3",
            "linetype": "Continuous",
            "lineweight": "0.35mm",
        },
        "revit": {
            "family_category": "Conduit",
            "family_name": "Conduit",
            "parameters": ["diameter_mm", "length_m", "conduit_type"],
        },
    },
    "Tray": {
        "autocad": {
            "entity_type": "polyline",
            "layer": "E-TRAY",
            "color": "4",
            "linetype": "Dashed2",
            "lineweight": "0.35mm",
        },
        "revit": {
            "family_category": "Cable Tray",
            "family_name": "CableTray",
            "parameters": ["width_mm", "length_m", "fill_percent"],
        },
    },
}


# ---------------------------------------------------------------------------
# Translation Engine
# ---------------------------------------------------------------------------


class TranslationEngine:
    """Bidirectional translation between all engineering platforms.

    Supports translations:
      - ETAP ↔ Unified Model
      - AutoCAD ↔ Unified Model
      - Revit ↔ Unified Model
      - ETAP ↔ AutoCAD (via Unified Model)
      - ETAP ↔ Revit (via Unified Model)
    """

    def __init__(self):
        self._translation_log: list[dict] = []

    # ------------------------------------------------------------------
    # Mapping rules
    # ------------------------------------------------------------------

    def get_drawing_rule(self, entity_type: str, target_system: str) -> dict:
        """Get the drawing rule for an entity type in the target system."""
        rules = ENTITY_DRAWING_RULES.get(entity_type, {})
        return rules.get(target_system, {})

    def get_all_mapping_rules(self) -> dict[str, dict]:
        """Get all mapping rules."""
        return ENTITY_DRAWING_RULES

    # ------------------------------------------------------------------
    # ETAP ↔ Unified Model
    # ------------------------------------------------------------------

    def etap_to_unified(self, etap_data: dict) -> dict:
        """Translate ETAP study results/data to the Unified Engineering Model.

        Parameters
        ----------
        etap_data : dict
            ETAP result data with sections for buses, branches, transformers,
            generators, loads, etc.

        Returns
        -------
        dict
            Unified Engineering Model compatible dictionary.
        """
        buses: list[Bus] = []
        transformers: list[Transformer] = []
        cables: list[Cable] = []
        generators: list[Generator] = []
        loads: list[Load] = []
        breakers: list[Breaker] = []
        panels: list[Panel] = []

        # Translate buses
        for bid, bus_data in etap_data.get("buses", {}).items():
            bus = Bus(
                id=str(bid),
                name=f"BUS_{bid}",
                bus_type=self._map_bus_type(bus_data.get("bus_type", "pq")),
                voltage_magnitude_pu=float(bus_data.get("voltage_magnitude", 1.0)),
                voltage_angle_deg=float(bus_data.get("voltage_angle", 0.0)),
                base_kv=float(bus_data.get("base_kv", 11.0)),
                load_mw=float(bus_data.get("active_power", 0.0)),
                load_mvar=float(bus_data.get("reactive_power", 0.0)),
                source_system=SourceSystem.ETAP,
            )
            buses.append(bus)
            self._log_translation("etap_to_unified", "bus", str(bid), bus.id)

        # Translate branches to cables
        for brid, _br_data in etap_data.get("branches", {}).items():
            cable = Cable(
                id=str(brid),
                name=f"CBL_{brid}",
                from_bus_id=str(brid.split("-")[0] if "-" in str(brid) else "1"),
                to_bus_id=str(brid.split("-")[1] if "-" in str(brid) else "2"),
                length_m=100.0,
                source_system=SourceSystem.ETAP,
            )
            cables.append(cable)
            self._log_translation("etap_to_unified", "cable", str(brid), cable.id)

        # Translate transformers
        for xfid, xf_data in etap_data.get("transformers", {}).items():
            xf = Transformer(
                id=str(xfid),
                name=f"XF_{xfid}",
                from_bus_id=str(xf_data.get("from_bus", "")),
                to_bus_id=str(xf_data.get("to_bus", "")),
                rated_power_mva=float(xf_data.get("rated_mva", 1.0)),
                impedance_percent=float(xf_data.get("impedance_percent", 5.75)),
                tap_ratio=float(xf_data.get("tap_ratio", 1.0)),
                source_system=SourceSystem.ETAP,
            )
            transformers.append(xf)

        return {
            "buses": [b.model_dump() for b in buses],
            "transformers": [t.model_dump() for t in transformers],
            "cables": [c.model_dump() for c in cables],
            "generators": [g.model_dump() for g in generators],
            "loads": [l.model_dump() for l in loads],
            "breakers": [b.model_dump() for b in breakers],
            "panels": [p.model_dump() for p in panels],
        }

    def unified_to_etap(self, unified_data: dict) -> dict:
        """Translate Unified Engineering Model data to ETAP format."""
        etap_data: dict = {
            "buses": {},
            "branches": {},
            "transformers": {},
            "generators": {},
            "loads": {},
        }

        for bus_data in unified_data.get("buses", []):
            bid = bus_data.get("id", "BUS1")
            etap_data["buses"][bid] = {
                "name": bus_data.get("name", bid),
                "voltage_magnitude": bus_data.get("voltage_magnitude_pu", 1.0),
                "voltage_angle": bus_data.get("voltage_angle_deg", 0.0),
                "bus_type": bus_data.get("bus_type", "pq"),
                "base_kv": bus_data.get("base_kv", 11.0),
                "active_power": bus_data.get("load_mw", 0.0),
                "reactive_power": bus_data.get("load_mvar", 0.0),
            }

        for cable_data in unified_data.get("cables", []):
            branch_id = f"{cable_data.get('from_bus_id', '')}-{cable_data.get('to_bus_id', '')}"
            etap_data["branches"][branch_id] = {
                "from_bus": cable_data.get("from_bus_id", ""),
                "to_bus": cable_data.get("to_bus_id", ""),
                "length_m": cable_data.get("length_m", 100.0),
                "r_ohm_per_km": cable_data.get("r_ohm_per_km", 0.0),
                "x_ohm_per_km": cable_data.get("x_ohm_per_km", 0.0),
            }

        return etap_data

    # ------------------------------------------------------------------
    # Unified Model → AutoCAD
    # ------------------------------------------------------------------

    def unified_to_autocad_commands(self, unified_data: dict) -> list[dict]:
        """Generate AutoCAD drawing commands from Unified Model data.

        Returns a list of command dicts that can be sent to the
        AutoCAD Plugin client in sequence.
        """
        commands: list[dict] = []
        options = {
            "start_x": 50,
            "start_y": 200,
            "bus_spacing_x": 150,
            "bus_spacing_y": 60,
        }

        # Create layers
        for layer_name in [
            "E-BUS",
            "E-XFMR",
            "E-CABLE",
            "E-BREAKER",
            "E-PANEL",
            "E-LOAD",
            "E-EQUIP",
            "E-ANNO",
        ]:
            commands.append(
                {
                    "command": "create_layer",
                    "params": {"name": layer_name, "color": "1", "linetype": "Continuous"},
                },
            )

        # Draw buses
        for i, bus_data in enumerate(unified_data.get("buses", [])):
            x = options["start_x"] + i * options["bus_spacing_x"]
            y = options["start_y"]
            commands.append(
                {
                    "command": "draw_electrical_symbol",
                    "params": {
                        "symbol_type": "bus",
                        "insertion_point": [x, y, 0],
                        "attributes": {
                            "BUS_ID": bus_data.get("id", ""),
                            "KV": str(bus_data.get("base_kv", "")),
                            "VMAG": f"{bus_data.get('voltage_magnitude_pu', 1.0):.3f}",
                        },
                    },
                },
            )

        # Draw cables
        for cable_data in unified_data.get("cables", []):
            from_bus = next(
                (
                    b
                    for b in unified_data.get("buses", [])
                    if b.get("id") == cable_data.get("from_bus_id")
                ),
                None,
            )
            to_bus = next(
                (
                    b
                    for b in unified_data.get("buses", [])
                    if b.get("id") == cable_data.get("to_bus_id")
                ),
                None,
            )
            if from_bus and to_bus:
                fx = (
                    options["start_x"]
                    + unified_data["buses"].index(from_bus) * options["bus_spacing_x"]
                    + 20
                )
                tx = (
                    options["start_x"]
                    + unified_data["buses"].index(to_bus) * options["bus_spacing_x"]
                    - 20
                )
                commands.append(
                    {
                        "command": "draw_polyline",
                        "params": {
                            "vertices": [[fx, options["start_y"], 0], [tx, options["start_y"], 0]],
                            "layer": "E-CABLE",
                        },
                    },
                )

        # Draw transformers
        for xf_data in unified_data.get("transformers", []):
            commands.append(
                {
                    "command": "draw_electrical_symbol",
                    "params": {
                        "symbol_type": "transformer",
                        "insertion_point": [150, 150, 0],
                        "attributes": {
                            "XF_ID": xf_data.get("id", ""),
                            "MVA": str(xf_data.get("rated_power_mva", "")),
                            "Z_PCT": str(xf_data.get("impedance_percent", "")),
                        },
                    },
                },
            )

        return commands

    # ------------------------------------------------------------------
    # ETAP ↔ AutoCAD (via Unified Model)
    # ------------------------------------------------------------------

    def etap_to_autocad(self, etap_data: dict) -> list[dict]:
        """Translate ETAP data directly to AutoCAD commands."""
        unified = self.etap_to_unified(etap_data)
        return self.unified_to_autocad_commands(unified)

    # ------------------------------------------------------------------
    # Revit ↔ Unified Model
    # ------------------------------------------------------------------

    def revit_to_unified(self, revit_data: dict) -> dict:
        """Translate Revit exported data to Unified Engineering Model."""
        unified: dict = {
            "project": {},
            "buses": [],
            "transformers": [],
            "cables": [],
            "panels": [],
            "loads": [],
            "equipment": [],
            "rooms": [],
            "levels": [],
        }

        # Translate levels
        for level_data in revit_data.get("levels", []):
            unified["levels"].append(
                {
                    "id": level_data.get("id", ""),
                    "name": level_data.get("name", ""),
                    "elevation_m": level_data.get("elevation", 0.0),
                },
            )

        # Translate rooms
        for room_data in revit_data.get("rooms", []):
            unified["rooms"].append(
                {
                    "id": room_data.get("id", ""),
                    "name": room_data.get("name", ""),
                    "area_sqm": room_data.get("area", 0.0),
                    "level_id": room_data.get("level_id", ""),
                },
            )

        # Translate MEP elements to unified model
        for element in revit_data.get("electrical_elements", []):
            category = element.get("category", "")
            if "panel" in category.lower() or "panelboard" in category.lower():
                unified["panels"].append(element)
            elif "transformer" in category.lower():
                unified["transformers"].append(element)
            elif "load" in category.lower() or "fixture" in category.lower():
                unified["loads"].append(element)
            elif "equipment" in category.lower():
                unified["equipment"].append(element)

        return unified

    def unified_to_revit_commands(self, unified_data: dict) -> list[dict]:
        """Generate Revit API commands from Unified Model data."""
        commands: list[dict] = []

        # Create levels
        for level_data in unified_data.get("levels", []):
            commands.append(
                {
                    "endpoint": "/level/create",
                    "payload": {
                        "name": level_data.get("name", "Level 1"),
                        "elevation": level_data.get("elevation_m", 0.0),
                    },
                },
            )

        # Create panels
        for panel_data in unified_data.get("panels", []):
            commands.append(
                {
                    "endpoint": "/element/create",
                    "payload": {
                        "element_type": "panel",
                        "params": {
                            "location": panel_data.get("location", [0, 0, 0]),
                            "parameters": panel_data,
                        },
                    },
                },
            )

        return commands

    # ------------------------------------------------------------------
    # Batch translation
    # ------------------------------------------------------------------

    def translate(self, source_system: str, target_system: str, data: dict) -> Any:
        """Generic translation dispatch.

        Parameters
        ----------
        source_system : str
            One of 'etap', 'autocad', 'revit', 'unified'
        target_system : str
            One of 'etap', 'autocad', 'revit', 'unified'
        data : dict
            Source data in the source system's format

        Returns
        -------
        Union[dict, list]
            Translated data in the target system's format
        """
        if source_system == "etap" and target_system == "unified":
            return self.etap_to_unified(data)
        elif source_system == "unified" and target_system == "etap":
            return self.unified_to_etap(data)
        elif source_system == "unified" and target_system == "autocad":
            return self.unified_to_autocad_commands(data)
        elif source_system == "etap" and target_system == "autocad":
            return self.etap_to_autocad(data)
        elif source_system == "revit" and target_system == "unified":
            return self.revit_to_unified(data)
        elif source_system == "unified" and target_system == "revit":
            return self.unified_to_revit_commands(data)
        else:
            logger.warning("Unsupported translation: %s → %s", source_system, target_system)
            return data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _map_bus_type(self, etap_type: str) -> str:
        mapping = {
            "swing": "slack",
            "ref": "slack",
            "gen": "pv",
            "load": "pq",
        }
        return mapping.get(etap_type.lower(), "pq")

    def _log_translation(
        self, direction: str, entity_type: str, source_id: str, target_id: str,
    ) -> None:
        self._translation_log.append(
            {
                "direction": direction,
                "entity_type": entity_type,
                "source_id": source_id,
                "target_id": target_id,
                "timestamp": __import__("time").time(),
            },
        )

    def get_translation_log(self, limit: int = 100) -> list[dict]:
        return self._translation_log[-limit:]

    def get_statistics(self) -> dict:
        total = len(self._translation_log)
        by_direction: dict = {}
        for op in self._translation_log:
            d = op["direction"]
            by_direction[d] = by_direction.get(d, 0) + 1
        return {
            "total_translations": total,
            "by_direction": by_direction,
        }
