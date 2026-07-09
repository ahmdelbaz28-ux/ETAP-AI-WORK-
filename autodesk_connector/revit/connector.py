"""
Revit Connector — Python Service Layer
=======================================
Orchestrates Revit BIM operations via the C# Revit Plugin.
Supports reading/writing Revit elements, families, parameters, and levels.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional, Union

import requests

from autodesk_connector.shared.models import (
    Conduit,
    Coordinates,
    Equipment,
    Level,
    Panel,
    Room,
    Tray,
    UnifiedEngineeringModel,
)
from compat import StrEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RevitElementType(StrEnum):
    WALL = "wall"
    FLOOR = "floor"
    CEILING = "ceiling"
    ROOF = "roof"
    DOOR = "door"
    WINDOW = "window"
    COLUMN = "column"
    BEAM = "beam"
    DUCT = "duct"
    PIPE = "pipe"
    CABLE_TRAY = "cable_tray"
    CONDUIT = "conduit"
    PANEL = "panel"
    SWITCHBOARD = "switchboard"
    TRANSFORMER = "transformer"
    GENERATOR = "generator"
    LIGHTING_FIXTURE = "lighting_fixture"
    ELECTRICAL_EQUIPMENT = "electrical_equipment"
    ELECTRICAL_FIXTURE = "electrical_fixture"
    DEVICE = "device"
    LEVEL = "level"
    ROOM = "room"
    SPACE = "space"
    FAMILY_INSTANCE = "family_instance"


# ---------------------------------------------------------------------------
# Revit Plugin Client
# ---------------------------------------------------------------------------


class RevitPluginClient:
    """HTTP client for the C# Revit Plugin running inside Revit."""

    def __init__(
        self,
        base_url: str = "http://localhost:4830",
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
            },
        )

    def is_available(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _call(self, endpoint: str, payload: Optional[dict] = None) -> dict:
        """Make an API call to the Revit plugin."""
        url = f"{self.base_url}/api{endpoint}"
        resp = self.session.post(url, json=payload or {}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def open_model(self, file_path: str) -> dict:
        return self._call("/model/open", {"file_path": file_path})

    def save_model(self, file_path: Optional[str] = None) -> dict:
        return self._call("/model/save", {"file_path": file_path or ""})

    def create_model(self, file_path: str, template: str = "") -> dict:
        return self._call("/model/create", {"file_path": file_path, "template": template})

    # ------------------------------------------------------------------
    # Elements
    # ------------------------------------------------------------------

    def create_element(self, element_type: str, params: dict) -> dict:
        return self._call("/element/create", {"element_type": element_type, "params": params})

    def update_element(self, element_id: str, params: dict) -> dict:
        return self._call("/element/update", {"element_id": element_id, "params": params})

    def delete_element(self, element_id: str) -> dict:
        return self._call("/element/delete", {"element_id": element_id})

    def read_element(self, element_id: str) -> dict:
        return self._call("/element/read", {"element_id": element_id})

    def list_elements(self, category: str = "", level_id: str = "") -> dict:
        return self._call("/element/list", {"category": category, "level_id": level_id})

    # ------------------------------------------------------------------
    # Families
    # ------------------------------------------------------------------

    def load_family(self, family_path: str) -> dict:
        return self._call("/family/load", {"family_path": family_path})

    def place_family(
        self, family_symbol: str, insertion_point: list[float], level_id: str = "",
    ) -> dict:
        return self._call(
            "/family/place",
            {
                "family_symbol": family_symbol,
                "insertion_point": insertion_point,
                "level_id": level_id,
            },
        )

    def list_families(self, category: str = "") -> dict:
        return self._call("/family/list", {"category": category})

    # ------------------------------------------------------------------
    # Parameters
    # ------------------------------------------------------------------

    def read_parameters(self, element_id: str) -> dict:
        return self._call("/parameter/read", {"element_id": element_id})

    def update_parameter(self, element_id: str, param_name: str, value: Any) -> dict:
        return self._call(
            "/parameter/update",
            {
                "element_id": element_id,
                "param_name": param_name,
                "value": value,
            },
        )

    # ------------------------------------------------------------------
    # Levels & Rooms
    # ------------------------------------------------------------------

    def create_level(self, name: str, elevation: float) -> dict:
        return self._call("/level/create", {"name": name, "elevation": elevation})

    def list_levels(self) -> dict:
        return self._call("/level/list", {})

    def create_room(self, name: str, level_id: str, bounding_box: Optional[dict] = None) -> dict:
        return self._call(
            "/room/create",
            {
                "name": name,
                "level_id": level_id,
                "bounding_box": bounding_box,
            },
        )

    def list_rooms(self, level_id: str = "") -> dict:
        return self._call("/room/list", {"level_id": level_id})

    # ------------------------------------------------------------------
    # MEP / Electrical
    # ------------------------------------------------------------------

    def read_electrical_systems(self) -> dict:
        return self._call("/mep/electrical_systems", {})

    def read_mep_data(self) -> dict:
        return self._call("/mep/data", {})

    def create_circuit(
        self, panel_id: str, device_ids: list[str], circuit_number: Optional[int] = None,
    ) -> dict:
        return self._call(
            "/mep/create_circuit",
            {
                "panel_id": panel_id,
                "device_ids": device_ids,
                "circuit_number": circuit_number,
            },
        )

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync_revit_to_model(self) -> dict:
        """Export current Revit state as a Unified Engineering Model JSON."""
        return self._call("/sync/to_model", {})

    def sync_model_to_revit(self, model_json: str) -> dict:
        """Import a Unified Engineering Model into Revit."""
        return self._call("/sync/from_model", {"model_json": model_json})

    def generate_electrical_documentation(self) -> dict:
        """Generate panel schedules, cable schedules, and BOM."""
        return self._call("/documentation/generate", {})


# ---------------------------------------------------------------------------
# Revit Connector
# ---------------------------------------------------------------------------


class RevitConnector:
    """High-level Revit connector for the Engineering Copilot.

    Orchestrates BIM model operations and maps Unified Engineering
    Models to Revit elements.
    """

    def __init__(self, plugin_url: str = "http://localhost:4830", api_key: str = ""):
        self.plugin = RevitPluginClient(plugin_url, api_key=api_key)
        self._current_model_path: Optional[str] = None
        self._operation_log: list[dict] = []

    @property
    def is_connected(self) -> bool:
        return self.plugin.is_available()

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def open_model(self, file_path: str) -> dict:
        result = self.plugin.open_model(file_path)
        if result.get("success"):
            self._current_model_path = file_path
        return result

    def create_model(self, file_path: str) -> dict:
        result = self.plugin.create_model(file_path)
        if result.get("success"):
            self._current_model_path = file_path
        return result

    def save_model(self) -> dict:
        return self.plugin.save_model(self._current_model_path)

    # ------------------------------------------------------------------
    # Unified Model → Revit Mapping
    # ------------------------------------------------------------------

    def create_level(self, level: Level) -> dict:
        """Create a Revit level from a unified Level model."""
        elevation = level.elevation_m or 0.0
        result = self.plugin.create_level(level.name, elevation)
        if result.get("success"):
            self._log_operation("create_level", level.name, True)
        return result

    def create_room(self, room: Room, level_id: str) -> dict:
        """Create a Revit room from a unified Room model."""
        area = room.area_sqm or 20.0
        bbox = {
            "min_x": room.coordinates.x if room.coordinates else 0,
            "min_y": room.coordinates.y if room.coordinates else 0,
            "max_x": (room.coordinates.x if room.coordinates else 0) + area**0.5,
            "max_y": (room.coordinates.y if room.coordinates else 0) + area**0.5,
        }
        return self.plugin.create_room(room.name, level_id, bounding_box=bbox)

    def place_panel(self, panel: Panel, level_id: str) -> dict:
        """Place an electrical panel family in Revit."""
        x = panel.coordinates.x if panel.coordinates else 0.0
        y = panel.coordinates.y if panel.coordinates else 0.0

        params = {
            "panel_name": panel.name,
            "panel_type": panel.panel_type.value,
            "voltage_v": panel.voltage_nominal_v,
            "phase_count": panel.phase_count,
            "main_rating_a": panel.main_breaker_a or 0,
            "bus_rating_a": panel.bus_rating_a or 0,
            "enclosure_type": panel.enclosure_type or "NEMA 1",
        }

        result = self.plugin.create_element(
            element_type=RevitElementType.PANEL.value,
            params={
                "location": [x, y, 0],
                "level_id": level_id,
                "parameters": params,
            },
        )
        if result.get("success"):
            self._log_operation("place_panel", panel.name, True)
        return result

    def place_equipment(self, equipment: Equipment, level_id: str, location: Coordinates) -> dict:
        """Place electrical equipment in Revit."""
        dims = equipment.dimensions or {}
        params = {
            "equipment_name": equipment.name,
            "category": equipment.equipment_category,
            "rated_kva": equipment.rated_power_kva or 0,
            "voltage_v": equipment.voltage_nominal_v or 0,
            "manufacturer": equipment.manufacturer or "",
            "model": equipment.model or "",
            "width_mm": dims.get("width_mm", 800),
            "depth_mm": dims.get("depth_mm", 600),
            "height_mm": dims.get("height_mm", 2000),
        }

        return self.plugin.create_element(
            element_type=RevitElementType.ELECTRICAL_EQUIPMENT.value,
            params={
                "location": [location.x, location.y, location.z],
                "level_id": level_id,
                "parameters": params,
            },
        )

    def create_cable_tray(self, tray: Tray, level_id: str) -> dict:
        """Create a cable tray run in Revit MEP."""
        params = {
            "tray_name": tray.name,
            "tray_type": tray.tray_type,
            "width_mm": tray.width_mm,
            "height_mm": tray.height_mm or tray.width_mm * 0.5,
            "length_m": tray.length_m,
            "material": tray.material,
        }
        if tray.routing_path:
            params["routing_path"] = [[p.x, p.y, p.z] for p in tray.routing_path]

        return self.plugin.create_element(
            element_type=RevitElementType.CABLE_TRAY.value,
            params={
                "level_id": level_id,
                "parameters": params,
            },
        )

    def create_conduit(self, conduit: Conduit, level_id: str) -> dict:
        """Create a conduit run in Revit MEP."""
        params = {
            "conduit_name": conduit.name,
            "conduit_type": conduit.conduit_type,
            "diameter_mm": conduit.diameter_mm,
            "length_m": conduit.length_m,
        }
        if conduit.routing_path:
            params["routing_path"] = [[p.x, p.y, p.z] for p in conduit.routing_path]

        return self.plugin.create_element(
            element_type=RevitElementType.CONDUIT.value,
            params={
                "level_id": level_id,
                "parameters": params,
            },
        )

    # ------------------------------------------------------------------
    # Bidirectional Sync
    # ------------------------------------------------------------------

    def export_to_unified_model(self) -> dict:
        """Export the current Revit model to a Unified Engineering Model."""
        return self.plugin.sync_revit_to_model()

    def import_from_unified_model(self, model: UnifiedEngineeringModel) -> dict:
        """Import a Unified Engineering Model into Revit."""
        model_json = model.to_json()
        return self.plugin.sync_model_to_revit(model_json)

    def synchronize(self, model: UnifiedEngineeringModel) -> dict:
        """Bidirectional sync: export Revit → update model → import back."""
        # Step 1: Export current Revit state
        export_result = self.export_to_unified_model()

        # Step 2: Merge with provided model
        operations = {
            "exported": export_result.get("success", False),
            "levels_created": 0,
            "rooms_created": 0,
            "elements_placed": 0,
        }

        # Step 3: Create levels
        for building in model.project.buildings:
            for level in building.levels:
                self.create_level(level)
                operations["levels_created"] += 1

                for room in level.rooms:
                    if level.id:
                        self.create_room(room, level.id)
                        operations["rooms_created"] += 1

        # Step 4: Place electrical elements
        for panel in model.project.panels:
            if model.project.buildings and model.project.buildings[0].levels:
                level_id = model.project.buildings[0].levels[0].id
                self.place_panel(panel, level_id)
                operations["elements_placed"] += 1

        # Step 5: Generate documentation
        doc_result = self.plugin.generate_electrical_documentation()

        return {
            "success": True,
            "export": export_result,
            "operations": operations,
            "documentation": doc_result,
        }

    # ------------------------------------------------------------------
    # Documentation
    # ------------------------------------------------------------------

    def generate_panel_schedules(self) -> dict:
        """Generate panel schedule sheets."""
        return self.plugin.generate_electrical_documentation()

    def generate_bill_of_materials(self) -> dict:
        """Generate BOM from Revit model."""
        result = self.plugin.read_electrical_systems()
        if not result.get("success"):
            return {"success": False, "error": "Failed to read electrical systems"}
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_operation(
        self, operation: str, target: str, success: bool, details: Optional[dict] = None,
    ) -> None:
        self._operation_log.append(
            {
                "operation": operation,
                "target": target,
                "success": success,
                "details": details or {},
                "timestamp": time.time(),
            },
        )

    def get_operation_log(self, limit: int = 100) -> list[dict]:
        return self._operation_log[-limit:]

    def get_statistics(self) -> dict:
        return {
            "connected": self.is_connected,
            "current_model": self._current_model_path,
            "total_operations": len(self._operation_log),
            "successful_operations": sum(1 for op in self._operation_log if op["success"]),
        }
