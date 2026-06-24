"""
AutoCAD Connector — Python Service Layer
=========================================
Orchestrates AutoCAD operations via the C# AutoCAD Plugin.
Provides high-level APIs for the Engineering Copilot.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Dict, List, Optional

import requests

from autodesk_connector.shared.models import (
    Annotation,
    Breaker,
    Bus,
    Cable,
    Coordinates,
    Equipment,
    Load,
    Panel,
    Transformer,
)
from compat import StrEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AutoCADEntityType(StrEnum):
    LINE = "line"
    POLYLINE = "polyline"
    CIRCLE = "circle"
    ARC = "arc"
    TEXT = "text"
    MTEXT = "mtext"
    BLOCK = "block"
    DYNAMIC_BLOCK = "dynamic_block"
    DIMENSION = "dimension"
    LAYER = "layer"
    HATCH = "hatch"
    ATTRIBUTE = "attribute"
    LEADER = "leader"
    TABLE = "table"


class AutoCADDrawingOperation(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"
    LIST = "list"
    BATCH = "batch"


# ---------------------------------------------------------------------------
# AutoCAD Drawing Context
# ---------------------------------------------------------------------------


class AutoCADDrawingContext:
    """Tracks the state of an open DWG drawing."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.layers: Dict[str, dict] = {}
        self.blocks: Dict[str, dict] = {}
        self.entities: List[dict] = []
        self.modified: bool = False
        self.locked: bool = False
        self.transaction_count: int = 0


# ---------------------------------------------------------------------------
# AutoCAD Plugin Client
# ---------------------------------------------------------------------------


class AutoCADPluginClient:
    """HTTP client for the C# AutoCAD Plugin running inside AutoCAD."""

    def __init__(
        self,
        base_url: str = "http://localhost:4820",
        timeout: int = 300,
        api_key: str = "",
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "X-API-Key": api_key,
            }
        )
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if the AutoCAD plugin is reachable."""
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def send_command(self, command: str, params: dict) -> dict:
        """Send a drawing command to the AutoCAD plugin."""
        resp = self.session.post(
            f"{self.base_url}/api/command",
            json={"command": command, "params": params},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def open_drawing(self, file_path: str) -> dict:
        """Open a DWG file in AutoCAD."""
        return self.send_command("open_drawing", {"file_path": file_path})

    def save_drawing(self, file_path: Optional[str] = None) -> dict:
        """Save the current drawing."""
        return self.send_command("save_drawing", {"file_path": file_path or ""})

    def create_drawing(self, file_path: str, template: str = "") -> dict:
        """Create a new DWG file."""
        return self.send_command(
            "create_drawing",
            {
                "file_path": file_path,
                "template": template,
            },
        )

    def create_layer(
        self, name: str, color: str = "7", linetype: str = "Continuous", lineweight: str = "Default"
    ) -> dict:
        """Create a new layer."""
        return self.send_command(
            "create_layer",
            {
                "name": name,
                "color": color,
                "linetype": linetype,
                "lineweight": lineweight,
            },
        )

    def create_block(
        self, name: str, entities: List[dict], base_point: Optional[List[float]] = None
    ) -> dict:
        """Create a block definition."""
        return self.send_command(
            "create_block",
            {
                "name": name,
                "entities": entities,
                "base_point": base_point or [0, 0, 0],
            },
        )

    def insert_block(
        self,
        block_name: str,
        insertion_point: List[float],
        scale: float = 1.0,
        rotation: float = 0.0,
    ) -> dict:
        """Insert a block reference."""
        return self.send_command(
            "insert_block",
            {
                "block_name": block_name,
                "insertion_point": insertion_point,
                "scale": scale,
                "rotation": rotation,
            },
        )

    def draw_line(self, start: List[float], end: List[float], layer: str = "0") -> dict:
        """Draw a line entity."""
        return self.send_command(
            "draw_line",
            {
                "start": start,
                "end": end,
                "layer": layer,
            },
        )

    def draw_polyline(
        self, vertices: List[List[float]], closed: bool = False, layer: str = "0"
    ) -> dict:
        """Draw a polyline."""
        return self.send_command(
            "draw_polyline",
            {
                "vertices": vertices,
                "closed": closed,
                "layer": layer,
            },
        )

    def draw_circle(self, center: List[float], radius: float, layer: str = "0") -> dict:
        """Draw a circle."""
        return self.send_command(
            "draw_circle",
            {
                "center": center,
                "radius": radius,
                "layer": layer,
            },
        )

    def draw_arc(
        self,
        center: List[float],
        radius: float,
        start_angle: float,
        end_angle: float,
        layer: str = "0",
    ) -> dict:
        """Draw an arc."""
        return self.send_command(
            "draw_arc",
            {
                "center": center,
                "radius": radius,
                "start_angle": start_angle,
                "end_angle": end_angle,
                "layer": layer,
            },
        )

    def draw_text(
        self,
        text: str,
        insertion_point: List[float],
        height: float = 2.5,
        rotation: float = 0.0,
        layer: str = "0",
    ) -> dict:
        """Draw a text entity."""
        return self.send_command(
            "draw_text",
            {
                "text": text,
                "insertion_point": insertion_point,
                "height": height,
                "rotation": rotation,
                "layer": layer,
            },
        )

    def draw_dimension(
        self,
        type_: str,
        def_point: List[float],
        text_point: List[float],
        text: str = "",
        layer: str = "0",
    ) -> dict:
        """Draw a dimension entity."""
        return self.send_command(
            "draw_dimension",
            {
                "type": type_,
                "def_point": def_point,
                "text_point": text_point,
                "text": text,
                "layer": layer,
            },
        )

    def read_entities(self, layer: str = "", entity_type: str = "") -> dict:
        """Read entities from the current drawing."""
        return self.send_command(
            "read_entities",
            {
                "layer": layer,
                "entity_type": entity_type,
            },
        )

    def read_geometry(self, entity_id: str) -> dict:
        """Read geometry of a specific entity."""
        return self.send_command("read_geometry", {"entity_id": entity_id})

    def read_attributes(self, block_id: str) -> dict:
        """Read attributes of a block reference."""
        return self.send_command("read_attributes", {"block_id": block_id})

    def delete_entity(self, entity_id: str) -> dict:
        """Delete an entity from the drawing."""
        return self.send_command("delete_entity", {"entity_id": entity_id})

    def update_entity(self, entity_id: str, properties: dict) -> dict:
        """Update entity properties."""
        return self.send_command(
            "update_entity",
            {
                "entity_id": entity_id,
                "properties": properties,
            },
        )

    def start_transaction(self) -> dict:
        """Start a database transaction."""
        return self.send_command("start_transaction", {})

    def commit_transaction(self) -> dict:
        """Commit the active transaction."""
        return self.send_command("commit_transaction", {})

    def rollback_transaction(self) -> dict:
        """Rollback the active transaction."""
        return self.send_command("rollback_transaction", {})

    def batch_operation(self, operations: List[dict]) -> List[dict]:
        """Execute multiple operations in a single transaction."""
        return self.send_command("batch", {"operations": operations})

    def export_dwg(self, source_path: str, output_path: str, format_: str = "dwg") -> dict:
        """Export DWG to another format (PDF, DWF, DXF)."""
        return self.send_command(
            "export",
            {
                "source_path": source_path,
                "output_path": output_path,
                "format": format_,
            },
        )

    def draw_electrical_symbol(
        self,
        symbol_type: str,
        insertion_point: List[float],
        scale: float = 1.0,
        rotation: float = 0.0,
        attributes: Optional[dict] = None,
    ) -> dict:
        """Draw an electrical component symbol."""
        return self.send_command(
            "draw_electrical_symbol",
            {
                "symbol_type": symbol_type,
                "insertion_point": insertion_point,
                "scale": scale,
                "rotation": rotation,
                "attributes": attributes or {},
            },
        )

    def draw_single_line_diagram(
        self, buses: List[dict], branches: List[dict], options: Optional[dict] = None
    ) -> dict:
        """Generate a single-line diagram from bus/branch data."""
        return self.send_command(
            "draw_single_line_diagram",
            {
                "buses": buses,
                "branches": branches,
                "options": options or {},
            },
        )


# ---------------------------------------------------------------------------
# AutoCAD Connector
# ---------------------------------------------------------------------------


class AutoCADConnector:
    """High-level AutoCAD connector for the Engineering Copilot.

    Manages the lifecycle of DWG drawings and maps Unified Engineering
    Models to AutoCAD entities.
    """

    def __init__(self, plugin_url: str = "http://localhost:4820", api_key: str = ""):
        self.plugin = AutoCADPluginClient(plugin_url, api_key=api_key)
        self._current_drawing: Optional[AutoCADDrawingContext] = None
        self._operation_log: List[dict] = []

    @property
    def is_connected(self) -> bool:
        return self.plugin.is_available()

    # ------------------------------------------------------------------
    # Drawing lifecycle
    # ------------------------------------------------------------------

    def open_drawing(self, file_path: str) -> dict:
        """Open a DWG file and set as current drawing."""
        result = self.plugin.open_drawing(file_path)
        if result.get("success"):
            self._current_drawing = AutoCADDrawingContext(file_path)
            self._log_operation("open_drawing", file_path, True)
        return result

    def save_drawing(self, file_path: Optional[str] = None) -> dict:
        result = self.plugin.save_drawing(file_path)
        if result.get("success") and self._current_drawing:
            self._current_drawing.modified = False
        return result

    def create_drawing(self, file_path: str, template: str = "") -> dict:
        result = self.plugin.create_drawing(file_path, template)
        if result.get("success"):
            self._current_drawing = AutoCADDrawingContext(file_path)
        return result

    def close_drawing(self) -> dict:
        self._current_drawing = None
        return {"success": True}

    # ------------------------------------------------------------------
    # Unified Model → AutoCAD Mapping
    # ------------------------------------------------------------------

    def draw_bus(self, bus: Bus, layer: str = "E-BUS") -> dict:
        """Draw a bus as an AutoCAD block."""
        x = bus.coordinates.x if bus.coordinates else 0.0
        y = bus.coordinates.y if bus.coordinates else 0.0

        attrs = {
            "BUS_ID": bus.id,
            "NAME": bus.name,
            "KV": f"{bus.base_kv:.1f}",
            "VMAG": f"{bus.voltage_magnitude_pu:.3f}",
            "VANG": f"{bus.voltage_angle_deg:.1f}",
            "TYPE": bus.bus_type.value.upper(),
        }

        return self.plugin.draw_electrical_symbol(
            symbol_type="bus",
            insertion_point=[x, y, 0],
            attributes=attrs,
        )

    def draw_transformer(self, transformer: Transformer, layer: str = "E-XFMR") -> dict:
        """Draw a transformer as a dynamic AutoCAD block."""
        x = transformer.coordinates.x if transformer.coordinates else 0.0
        y = transformer.coordinates.y if transformer.coordinates else 0.0

        attrs = {
            "XF_ID": transformer.id,
            "NAME": transformer.name,
            "MVA": f"{transformer.rated_power_mva:.1f}",
            "KV_PRIM": str(transformer.primary_voltage_kv or ""),
            "KV_SEC": str(transformer.secondary_voltage_kv or ""),
            "Z_PCT": f"{transformer.impedance_percent:.2f}"
            if transformer.impedance_percent
            else "",
            "TAP": f"{transformer.tap_ratio:.3f}",
        }

        return self.plugin.draw_electrical_symbol(
            symbol_type="transformer",
            insertion_point=[x, y, 0],
            attributes=attrs,
        )

    def draw_cable(self, cable: Cable, layer: str = "E-CABLE") -> dict:
        """Draw a cable as a polyline between two points."""
        if cable.routing_path and len(cable.routing_path) >= 2:
            vertices = [[p.x, p.y, p.z] for p in cable.routing_path]
        else:
            from_pt = cable.metadata.get("from_point", [0, 0, 0])
            to_pt = cable.metadata.get("to_point", [100, 0, 0])
            vertices = [from_pt, to_pt]

        self.plugin.create_layer(layer, color="3", linetype="Dashed")
        return self.plugin.draw_polyline(
            vertices=vertices,
            closed=False,
            layer=layer,
        )

    def draw_breaker(self, breaker: Breaker, layer: str = "E-BREAKER") -> dict:
        """Draw a breaker as an AutoCAD block."""
        x = breaker.coordinates.x if breaker.coordinates else 0.0
        y = breaker.coordinates.y if breaker.coordinates else 0.0

        attrs = {
            "BRK_ID": breaker.id,
            "NAME": breaker.name,
            "RATED_A": str(breaker.rated_current_a),
            "INTERRUPT_KA": str(breaker.interrupting_rating_ka),
            "POLES": str(breaker.poles),
            "TYPE": breaker.breaker_type.value.upper(),
        }

        return self.plugin.draw_electrical_symbol(
            symbol_type="breaker",
            insertion_point=[x, y, 0],
            attributes=attrs,
        )

    def draw_panel(self, panel: Panel, layer: str = "E-PANEL") -> dict:
        """Draw a panel as an AutoCAD block with schedule."""
        x = panel.coordinates.x if panel.coordinates else 0.0
        y = panel.coordinates.y if panel.coordinates else 0.0

        attrs = {
            "PANEL_ID": panel.id,
            "NAME": panel.name,
            "TYPE": panel.panel_type.value,
            "VOLTAGE_V": str(panel.voltage_nominal_v),
            "MAIN_A": str(panel.main_breaker_a or ""),
            "BUS_A": str(panel.bus_rating_a or ""),
            "PHASES": str(panel.phase_count),
            "ENCLOSURE": panel.enclosure_type or "",
        }

        return self.plugin.draw_electrical_symbol(
            symbol_type="panel",
            insertion_point=[x, y, 0],
            attributes=attrs,
        )

    def draw_load(self, load: Load, layer: str = "E-LOAD") -> dict:
        """Draw a load as an AutoCAD block."""
        x = load.coordinates.x if load.coordinates else 0.0
        y = load.coordinates.y if load.coordinates else 0.0

        attrs = {
            "LOAD_ID": load.id,
            "NAME": load.name,
            "KW": f"{load.rated_power_kw:.1f}",
            "PF": f"{load.power_factor:.2f}",
            "TYPE": load.load_type.value,
            "CATEGORY": load.load_category,
        }

        return self.plugin.draw_electrical_symbol(
            symbol_type="load",
            insertion_point=[x, y, 0],
            attributes=attrs,
        )

    def draw_equipment(self, equipment: Equipment, layer: str = "E-EQUIP") -> dict:
        """Draw general equipment as an AutoCAD block."""
        x = equipment.coordinates.x if equipment.coordinates else 0.0
        y = equipment.coordinates.y if equipment.coordinates else 0.0

        dims = equipment.dimensions or {}
        attrs = {
            "EQ_ID": equipment.id,
            "NAME": equipment.name,
            "CATEGORY": equipment.equipment_category,
            "KVA": str(equipment.rated_power_kva or ""),
            "VOLT": str(equipment.voltage_nominal_v or ""),
            "W(mm)": str(dims.get("width_mm", "")),
            "D(mm)": str(dims.get("depth_mm", "")),
            "H(mm)": str(dims.get("height_mm", "")),
        }

        return self.plugin.draw_electrical_symbol(
            symbol_type="equipment",
            insertion_point=[x, y, 0],
            attributes=attrs,
        )

    def draw_annotation(self, annotation: Annotation, layer: str = "E-ANNO") -> dict:
        """Draw a text annotation or dimension."""
        x = annotation.coordinates.x if annotation.coordinates else 0.0
        y = annotation.coordinates.y if annotation.coordinates else 0.0

        if annotation.annotation_type == "dimension":
            return self.plugin.draw_dimension(
                type_="aligned",
                def_point=[x, y, 0],
                text_point=[x + 50, y + 10, 0],
                text=annotation.text,
                layer=layer,
            )
        return self.plugin.draw_text(
            text=annotation.text,
            insertion_point=[x, y, 0],
            height=annotation.font_size,
            rotation=annotation.rotation_deg,
            layer=layer,
        )

    # ------------------------------------------------------------------
    # Single Line Diagram Generation
    # ------------------------------------------------------------------

    def generate_single_line_diagram(
        self,
        buses: List[Bus],
        transformers: List[Transformer],
        cables: List[Cable],
        breakers: List[Breaker],
        loads: List[Load],
        output_path: str,
        options: Optional[dict] = None,
    ) -> dict:
        """Generate a complete single-line diagram from the unified model.

        Creates layers, draws buses, transformers, cables, breakers, loads,
        and annotations. Arranges elements in a logical left-to-right layout.
        """
        opts = options or {}
        start_x = opts.get("start_x", 50)
        start_y = opts.get("start_y", 200)
        bus_spacing_x = opts.get("bus_spacing_x", 150)
        bus_spacing_y = opts.get("bus_spacing_y", 60)

        self.create_drawing(output_path)
        self._setup_electrical_layers()

        # Create title block
        title = Annotation(
            id=str(uuid.uuid4()),
            name="Title",
            annotation_type="label",
            text=f"Single Line Diagram — {opts.get('project_name', 'Project')}",
            font_size=5.0,
            coordinates=Coordinates(x=start_x, y=start_y + bus_spacing_y * 2),
        )
        self.draw_annotation(title, layer="E-TITLE")

        # Draw source (first bus) on the left
        for i, bus in enumerate(buses):
            bus.coordinates = Coordinates(
                x=start_x + i * bus_spacing_x,
                y=start_y,
            )
            self.draw_bus(bus)

        # Draw transformers connected to buses
        for xf in transformers:
            self.draw_transformer(xf)

        # Draw cables as lines between buses
        for cable in cables:
            from_bus = next((b for b in buses if b.id == cable.from_bus_id), None)
            to_bus = next((b for b in buses if b.id == cable.to_bus_id), None)
            if from_bus and to_bus:
                cable.routing_path = [
                    Coordinates(x=from_bus.coordinates.x + 20, y=from_bus.coordinates.y),
                    Coordinates(x=to_bus.coordinates.x - 20, y=to_bus.coordinates.y),
                ]
                self.draw_cable(cable)

        # Draw breakers
        for breaker in breakers:
            self.draw_breaker(breaker)

        # Draw loads
        for load in loads:
            self.draw_load(load)

        # Annotation with legend
        legend = Annotation(
            id=str(uuid.uuid4()),
            name="Legend",
            annotation_type="label",
            text=f"Generated: {time.strftime('%Y-%m-%d %H:%M')} | "
            f"Base: {opts.get('base_mva', 100)} MVA | "
            f"System: {opts.get('frequency', 60)} Hz",
            font_size=2.5,
            coordinates=Coordinates(x=start_x, y=start_y - bus_spacing_y),
        )
        self.draw_annotation(legend)

        self.save_drawing()

        return {
            "success": True,
            "output_path": output_path,
            "buses_drawn": len(buses),
            "transformers_drawn": len(transformers),
            "cables_drawn": len(cables),
            "breakers_drawn": len(breakers),
            "loads_drawn": len(loads),
        }

    def _setup_electrical_layers(self):
        """Create standard electrical layers for the drawing."""
        layers = {
            "E-BUS": ("1", "Continuous", "0.50mm"),
            "E-XFMR": ("2", "Continuous", "0.35mm"),
            "E-CABLE": ("3", "Dashed", "0.25mm"),
            "E-BREAKER": ("4", "Continuous", "0.35mm"),
            "E-PANEL": ("5", "Continuous", "0.35mm"),
            "E-LOAD": ("6", "Continuous", "0.25mm"),
            "E-EQUIP": ("7", "Continuous", "0.35mm"),
            "E-ANNO": ("8", "Continuous", "0.18mm"),
            "E-TITLE": ("9", "Continuous", "0.50mm"),
            "E-DIM": ("3", "Continuous", "0.18mm"),
        }
        for name, (color, lt, lw) in layers.items():
            try:
                self.plugin.create_layer(name, color=color, linetype=lt, lineweight=lw)
            except Exception:
                logger.debug(f"Layer {name} may already exist")

    # ------------------------------------------------------------------
    # Operations Log
    # ------------------------------------------------------------------

    def _log_operation(
        self, operation: str, target: str, success: bool, details: Optional[dict] = None
    ) -> None:
        self._operation_log.append(
            {
                "operation": operation,
                "target": target,
                "success": success,
                "details": details or {},
                "timestamp": time.time(),
            }
        )

    def get_operation_log(self, limit: int = 100) -> List[dict]:
        return self._operation_log[-limit:]

    def get_statistics(self) -> dict:
        return {
            "connected": self.is_connected,
            "current_drawing": self._current_drawing.file_path if self._current_drawing else None,
            "total_operations": len(self._operation_log),
            "successful_operations": sum(1 for op in self._operation_log if op["success"]),
        }
