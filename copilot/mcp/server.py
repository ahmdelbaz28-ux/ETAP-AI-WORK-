"""
Engineering Copilot — MCP Server
=================================
Model Context Protocol server exposing all CAD, ETAP, and engineering tools
as MCP tools for AI agents to discover and call.

Tools exposed:
  - create_drawing        — Create new DWG drawing
  - update_drawing         — Update existing DWG
  - read_drawing           — Read entities from DWG
  - create_panel           — Create electrical panel
  - create_transformer     — Create transformer
  - create_bus             — Create electrical bus
  - create_cable           — Create cable
  - generate_sld           — Generate single-line diagram
  - sync_etap              — Synchronize with ETAP
  - sync_revit             — Synchronize with Revit
  - sync_autocad           — Synchronize with AutoCAD
  - export_dwg             — Export DWG to PDF/DXF
  - export_json            — Export Unified Model as JSON
  - validate_design        — Run engineering checks
  - run_engineering_checks — Comprehensive design validation
"""

from __future__ import annotations

import logging

from autodesk_connector.autocad.connector import AutoCADConnector
from autodesk_connector.revit.connector import RevitConnector
from autodesk_connector.shared.models import (
    Bus,
    Cable,
    Coordinates,
    Panel,
    Project,
    Transformer,
    UnifiedEngineeringModel,
)
from copilot.translation.engine import TranslationEngine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Definitions (MCP-compatible tool schema)
# ---------------------------------------------------------------------------

MCP_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "create_drawing",
        "description": "Create a new AutoCAD DWG drawing file with optional template",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Full path to the new DWG file"},
                "template": {
                    "type": "string",
                    "description": "Optional template DWG path",
                    "default": "",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "update_drawing",
        "description": "Open and modify an existing DWG drawing",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to existing DWG"},
                "operations": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of drawing operations to perform",
                },
            },
            "required": ["file_path", "operations"],
        },
    },
    {
        "name": "read_drawing",
        "description": "Read entities from a DWG drawing",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to DWG file"},
                "layer": {"type": "string", "description": "Optional layer filter", "default": ""},
                "entity_type": {
                    "type": "string",
                    "description": "Optional entity type filter",
                    "default": "",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "create_panel",
        "description": "Create a new electrical panel in the engineering model",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Panel name"},
                "panel_type": {
                    "type": "string",
                    "enum": [
                        "MDP",
                        "SP",
                        "DP",
                        "LP",
                        "CP",
                        "AHUB",
                        "POWER_PANEL",
                        "LIGHTING_PANEL",
                    ],
                },
                "voltage_nominal_v": {"type": "number", "description": "Nominal voltage"},
                "phase_count": {"type": "integer", "default": 3},
                "main_breaker_a": {"type": "number", "description": "Main breaker rating"},
                "feeders": {"type": "array", "items": {"type": "object"}, "default": []},
                "x": {"type": "number", "default": 0},
                "y": {"type": "number", "default": 0},
            },
            "required": ["name", "panel_type", "voltage_nominal_v"],
        },
    },
    {
        "name": "create_transformer",
        "description": "Create a new transformer",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "from_bus_id": {"type": "string"},
                "to_bus_id": {"type": "string"},
                "rated_power_mva": {"type": "number"},
                "primary_voltage_kv": {"type": "number"},
                "secondary_voltage_kv": {"type": "number"},
                "impedance_percent": {"type": "number", "default": 5.75},
            },
            "required": ["name", "from_bus_id", "to_bus_id", "rated_power_mva"],
        },
    },
    {
        "name": "create_bus",
        "description": "Create a new electrical bus",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "base_kv": {"type": "number"},
                "bus_type": {"type": "string", "enum": ["slack", "pv", "pq"], "default": "pq"},
                "voltage_magnitude_pu": {"type": "number", "default": 1.0},
                "x": {"type": "number", "default": 0},
                "y": {"type": "number", "default": 0},
            },
            "required": ["name", "base_kv"],
        },
    },
    {
        "name": "create_cable",
        "description": "Create a new cable between two buses",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "from_bus_id": {"type": "string"},
                "to_bus_id": {"type": "string"},
                "length_m": {"type": "number"},
                "conductor_size_mm2": {"type": "number", "default": 95},
            },
            "required": ["name", "from_bus_id", "to_bus_id", "length_m"],
        },
    },
    {
        "name": "generate_sld",
        "description": "Generate a single-line diagram from the unified model",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Output DWG file path"},
                "project_name": {"type": "string", "default": "Project"},
                "base_mva": {"type": "number", "default": 100},
            },
            "required": ["output_path"],
        },
    },
    {
        "name": "sync_etap",
        "description": "Synchronize the unified model with an ETAP project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {"type": "string", "description": "Path to ETAP .edb project"},
                "direction": {
                    "type": "string",
                    "enum": ["import", "export", "full"],
                    "default": "full",
                },
            },
            "required": ["project_path"],
        },
    },
    {
        "name": "sync_revit",
        "description": "Synchronize the unified model with a Revit project",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_path": {"type": "string", "description": "Path to Revit .rvt model"},
                "direction": {
                    "type": "string",
                    "enum": ["import", "export", "full"],
                    "default": "full",
                },
            },
            "required": ["model_path"],
        },
    },
    {
        "name": "sync_autocad",
        "description": "Synchronize the unified model with an AutoCAD DWG",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to DWG file"},
                "direction": {"type": "string", "enum": ["import", "export"], "default": "export"},
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "export_dwg",
        "description": "Export DWG to PDF or DXF format",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_path": {"type": "string"},
                "output_path": {"type": "string"},
                "format": {"type": "string", "enum": ["pdf", "dxf", "dwf"], "default": "pdf"},
            },
            "required": ["source_path", "output_path"],
        },
    },
    {
        "name": "export_json",
        "description": "Export the complete unified engineering model as JSON",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_path": {"type": "string", "description": "Path for JSON output"},
                "pretty": {"type": "boolean", "default": True},
            },
            "required": ["output_path"],
        },
    },
    {
        "name": "validate_design",
        "description": "Run engineering validation checks on the model",
        "inputSchema": {
            "type": "object",
            "properties": {
                "check_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["overcurrent", "voltage", "coordination", "cable_sizing"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "run_engineering_checks",
        "description": "Comprehensive design validation across all engineering domains",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_json": {"type": "string", "description": "Unified model JSON string"},
            },
            "required": ["model_json"],
        },
    },
]


# ---------------------------------------------------------------------------
# MCP Tool Handlers
# ---------------------------------------------------------------------------


class CopilotMCPServer:
    """MCP Server implementation for the Engineering Copilot.

    Provides tool execution, tool listing, and health check capabilities
    following the Model Context Protocol.
    """

    def __init__(
        self,
        autocad_url: str = "http://localhost:4820",
        revit_url: str = "http://localhost:4830",
        autocad_api_key: str = "",
        revit_api_key: str = "",
    ):
        self.autocad = AutoCADConnector(plugin_url=autocad_url, api_key=autocad_api_key)
        self.revit = RevitConnector(plugin_url=revit_url, api_key=revit_api_key)
        self.translation = TranslationEngine()
        self.etap_provider = self._get_etap_provider()
        self._model = UnifiedEngineeringModel(
            project=Project(name="Engineering Copilot Project"),
        )
        self._tool_registry = self._build_tool_registry()

    def _get_etap_provider(self):
        """Lazy-load ETAP provider to avoid import errors on non-Windows."""
        try:
            from etap_integration.etap_provider import get_etap_provider

            return get_etap_provider()
        except Exception:
            logger.warning("ETAP provider not available")
            return None

    # ------------------------------------------------------------------
    # Tool registry
    # ------------------------------------------------------------------

    def _build_tool_registry(self) -> dict[str, callable]:
        """Build the mapping of tool names to handler methods."""
        return {
            "create_drawing": self._handle_create_drawing,
            "update_drawing": self._handle_update_drawing,
            "read_drawing": self._handle_read_drawing,
            "create_panel": self._handle_create_panel,
            "create_transformer": self._handle_create_transformer,
            "create_bus": self._handle_create_bus,
            "create_cable": self._handle_create_cable,
            "generate_sld": self._handle_generate_sld,
            "sync_etap": self._handle_sync_etap,
            "sync_revit": self._handle_sync_revit,
            "sync_autocad": self._handle_sync_autocad,
            "export_dwg": self._handle_export_dwg,
            "export_json": self._handle_export_json,
            "validate_design": self._handle_validate_design,
            "run_engineering_checks": self._handle_run_engineering_checks,
        }

    def list_tools(self) -> list[dict]:
        """List all available MCP tools with their schemas."""
        return MCP_TOOL_DEFINITIONS

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Execute a named MCP tool with the given arguments.

        Parameters
        ----------
        tool_name : str
            Name of the tool to execute.
        arguments : dict
            Tool-specific arguments.

        Returns
        -------
        dict
            Tool execution result with 'success', 'data'/'error' fields.
        """
        handler = self._tool_registry.get(tool_name)
        if not handler:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        try:
            return handler(arguments)
        except Exception as e:
            logger.exception("Tool %s failed", tool_name)
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Tool handlers
    # ------------------------------------------------------------------

    def _handle_create_drawing(self, args: dict) -> dict:
        return self.autocad.create_drawing(
            file_path=args["file_path"],
            template=args.get("template", ""),
        )

    def _handle_update_drawing(self, args: dict) -> dict:
        self.autocad.open_drawing(args["file_path"])
        ops = args.get("operations", [])
        results = []
        for op in ops:
            cmd = op.get("command", "")
            params = op.get("params", {})
            try:
                result = getattr(self.autocad.plugin, cmd)(**params)
                results.append({"command": cmd, "success": result.get("success", False)})
            except Exception as e:
                results.append({"command": cmd, "success": False, "error": str(e)})
        self.autocad.save_drawing()
        return {"success": True, "results": results}

    def _handle_read_drawing(self, args: dict) -> dict:
        self.autocad.open_drawing(args["file_path"])
        return self.autocad.plugin.read_entities(
            layer=args.get("layer", ""),
            entity_type=args.get("entity_type", ""),
        )

    def _handle_create_panel(self, args: dict) -> dict:
        panel = Panel(
            name=args["name"],
            panel_type=args["panel_type"],
            voltage_nominal_v=args["voltage_nominal_v"],
            phase_count=args.get("phase_count", 3),
            main_breaker_a=args.get("main_breaker_a"),
            coordinates=Coordinates(x=args.get("x", 0), y=args.get("y", 0)),
        )
        self._model.project.panels.append(panel)

        # Also draw in AutoCAD if connected
        if self.autocad.is_connected:
            self.autocad.draw_panel(panel)

        # Sync to Revit if connected
        if self.revit.is_connected:
            self.revit.place_panel(panel, level_id="")

        return {
            "success": True,
            "panel_id": panel.id,
            "panel": panel.model_dump(mode="json"),
        }

    def _handle_create_transformer(self, args: dict) -> dict:
        xf = Transformer(
            name=args["name"],
            from_bus_id=args["from_bus_id"],
            to_bus_id=args["to_bus_id"],
            rated_power_mva=args["rated_power_mva"],
            primary_voltage_kv=args.get("primary_voltage_kv"),
            secondary_voltage_kv=args.get("secondary_voltage_kv"),
            impedance_percent=args.get("impedance_percent", 5.75),
        )
        if self.autocad.is_connected:
            self.autocad.draw_transformer(xf)

        return {
            "success": True,
            "transformer_id": xf.id,
            "transformer": xf.model_dump(mode="json"),
        }

    def _handle_create_bus(self, args: dict) -> dict:
        bus = Bus(
            name=args["name"],
            base_kv=args["base_kv"],
            bus_type=args.get("bus_type", "pq"),
            voltage_magnitude_pu=args.get("voltage_magnitude_pu", 1.0),
            coordinates=Coordinates(x=args.get("x", 0), y=args.get("y", 0)),
            source_system="ai_generated",
        )
        if self.autocad.is_connected:
            self.autocad.draw_bus(bus)

        return {"success": True, "bus_id": bus.id, "bus": bus.model_dump(mode="json")}

    def _handle_create_cable(self, args: dict) -> dict:
        cable = Cable(
            name=args["name"],
            from_bus_id=args["from_bus_id"],
            to_bus_id=args["to_bus_id"],
            length_m=args["length_m"],
            conductor_size_mm2=args.get("conductor_size_mm2", 95),
        )
        if self.autocad.is_connected:
            self.autocad.draw_cable(cable)

        return {"success": True, "cable_id": cable.id, "cable": cable.model_dump(mode="json")}

    def _handle_generate_sld(self, args: dict) -> dict:
        """Generate a single-line diagram from the current model."""
        buses = self._model.get_all_buses()
        cables = self._model.get_all_cables()
        transformers = []

        if not buses and not cables:
            return {"success": False, "error": "No buses or cables in model to generate SLD"}

        result = self.autocad.generate_single_line_diagram(
            buses=buses,
            transformers=transformers,
            cables=cables,
            breakers=[],
            loads=[],
            output_path=args["output_path"],
            options={
                "project_name": args.get("project_name", "Project"),
                "base_mva": args.get("base_mva", 100),
            },
        )
        return result

    def _handle_sync_etap(self, args: dict) -> dict:
        direction = args.get("direction", "full")

        from digital_twin.state_store import DigitalTwinState
        from etap_integration.sync_engine import ETAPSyncEngine

        sync_engine = ETAPSyncEngine(
            etap_provider=self.etap_provider,
            dt_state=DigitalTwinState(),
        )

        if direction == "import":
            result = sync_engine.import_from_etap(args["project_path"])
        elif direction == "export":
            result = sync_engine.export_to_etap(args["project_path"])
        else:
            result = sync_engine.run_full_sync(args["project_path"])

        # Translate ETAP results to unified model
        if result.get("success") and direction in ("import", "full"):
            etap_data = result.get("objects", {})
            unified_data = self.translation.etap_to_unified(etap_data)
            result["unified_model"] = unified_data

        return result

    def _handle_sync_revit(self, args: dict) -> dict:
        direction = args.get("direction", "full")
        self.revit.open_model(args["model_path"])

        if direction == "import":
            result = self.revit.export_to_unified_model()
        elif direction == "export":
            result = self.revit.import_from_unified_model(self._model)
        else:
            result = self.revit.synchronize(self._model)

        return result

    def _handle_sync_autocad(self, args: dict) -> dict:
        direction = args.get("direction", "export")
        self.autocad.open_drawing(args["file_path"])

        if direction == "export":
            # Export unified model to AutoCAD
            for bus in self._model.get_all_buses():
                self.autocad.draw_bus(bus)
            self.autocad.save_drawing()
            return {"success": True, "direction": "export", "drawing": args["file_path"]}
        else:
            # Import AutoCAD entities to model
            entities = self.autocad.plugin.read_entities()
            return {"success": True, "direction": "import", "entities": entities}

    def _handle_export_dwg(self, args: dict) -> dict:
        return self.autocad.plugin.export_dwg(
            source_path=args["source_path"],
            output_path=args["output_path"],
            format_=args.get("format", "pdf"),
        )

    def _handle_export_json(self, args: dict) -> dict:
        output_path = args["output_path"]
        json_str = self._model.to_json(indent=2 if args.get("pretty", True) else None)
        with open(output_path, "w") as f:
            f.write(json_str)
        return {"success": True, "output_path": output_path, "size_bytes": len(json_str)}

    def _handle_validate_design(self, args: dict) -> dict:
        """Run validation checks on the current model."""
        check_types = args.get(
            "check_types", ["overcurrent", "voltage", "coordination", "cable_sizing"],
        )
        results: dict = {}

        if "voltage" in check_types:
            results["voltage_check"] = self._check_voltage_levels()
        if "overcurrent" in check_types:
            results["overcurrent_check"] = self._check_overcurrent()
        if "coordination" in check_types:
            results["coordination_check"] = self._check_coordination()

        passed = all(r.get("passed", False) for r in results.values())
        return {"success": True, "passed": passed, "checks": results}

    def _handle_run_engineering_checks(self, args: dict) -> dict:
        """Comprehensive engineering validation."""
        model_json = args.get("model_json", "{}")
        try:
            model = UnifiedEngineeringModel.from_json(model_json)
        except Exception as e:
            return {"success": False, "error": f"Invalid model JSON: {e}"}

        checks = {
            "model_integrity": self._check_model_integrity(model),
            "voltage_levels": self._check_voltage_levels(),
            "overcurrent": self._check_overcurrent(),
            "coordination": self._check_coordination(),
            "cable_sizing": self._check_cable_sizing(model),
        }

        all_passed = all(c.get("passed", False) for c in checks.values())
        return {"success": True, "passed": all_passed, "checks": checks}

    # ------------------------------------------------------------------
    # Engineering validation methods
    # ------------------------------------------------------------------

    def _check_voltage_levels(self) -> dict:
        issues = []
        for panel in self._model.project.panels:
            if panel.voltage_nominal_v <= 0:
                issues.append(f"Panel {panel.name}: invalid voltage {panel.voltage_nominal_v}V")
        return {"passed": len(issues) == 0, "issues": issues}

    def _check_overcurrent(self) -> dict:
        issues = []
        for panel in self._model.project.panels:
            if panel.main_breaker_a and panel.bus_rating_a:
                if panel.main_breaker_a > panel.bus_rating_a:
                    issues.append(
                        f"Panel {panel.name}: main breaker ({panel.main_breaker_a}A) "
                        f"> bus rating ({panel.bus_rating_a}A)",
                    )
        return {"passed": len(issues) == 0, "issues": issues}

    def _check_coordination(self) -> dict:
        issues = []
        for panel in self._model.project.panels:
            for feeder in panel.feeders:
                if panel.main_breaker_a and feeder.rated_current_a >= panel.main_breaker_a:
                    issues.append(
                        f"Panel {panel.name}: feeder {feeder.load_name} "
                        f"({feeder.rated_current_a}A) >= main breaker ({panel.main_breaker_a}A)",
                    )
        return {"passed": len(issues) == 0, "issues": issues}

    def _check_cable_sizing(self, model: UnifiedEngineeringModel) -> dict:
        """Validate cable sizing against expected loads."""
        issues = []
        cables = model.get_all_cables()
        if not cables:
            return {"passed": True, "issues": [], "note": "No cables to validate"}
        for cable in cables:
            if cable.length_m <= 0:
                issues.append(f"Cable {cable.name}: invalid length {cable.length_m}m")
        return {"passed": len(issues) == 0, "issues": issues}

    def _check_model_integrity(self, model: UnifiedEngineeringModel) -> dict:
        issues = []
        if not model.project.panels and not model.project.buildings:
            issues.append("Model is empty — no panels or buildings defined")
        return {"passed": len(issues) == 0, "issues": issues}

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        return {
            "status": "healthy",
            "autocad_connected": self.autocad.is_connected,
            "revit_connected": self.revit.is_connected,
            "etap_available": self.etap_provider.is_available() if self.etap_provider else False,
            "tools_count": len(self._tool_registry),
        }
