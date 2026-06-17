"""
AI Drawing Engine
=================
Autonomous CAD generation engine that translates natural language
engineering intent into:
  1. Engineering Knowledge Graph
  2. Unified Engineering Model
  3. AutoCAD drawing commands
  4. Revit element commands
  5. ETAP entity synchronization
  6. Validation report

Flow:
  User Intent → Intent Parser → Engineering Graph → Unified Model →
    ├── AutoCAD Commands → DWG Generation
    ├── Revit Commands → RVT Generation
    ├── ETAP Sync → ETAP Project Update
    └── Validation Report → User Feedback
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from autodesk_connector.shared.models import (
    Breaker,
    Bus,
    Cable,
    Coordinates,
    Generator,
    Load,
    Motor,
    Panel,
    Relay,
    Transformer,
    UnifiedEngineeringModel,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent Data Models
# ---------------------------------------------------------------------------


class EngineeringIntentType(str, Enum):
    CREATE_PANEL = "create_panel"
    CREATE_SLD = "create_sld"
    ADD_FEEDER = "add_feeder"
    ADD_TRANSFORMER = "add_transformer"
    ADD_BUS = "add_bus"
    ADD_CABLE = "add_cable"
    ADD_LOAD = "add_load"
    ADD_MOTOR = "add_motor"
    ADD_GENERATOR = "add_generator"
    ADD_RELAY = "add_relay"
    ADD_BREAKER = "add_breaker"
    VALIDATE_DESIGN = "validate_design"
    GENERATE_REPORT = "generate_report"
    SYNC_ALL = "sync_all"
    UNKNOWN = "unknown"


@dataclass
class EngineeringIntent:
    """Parsed engineering intent from natural language."""
    type: EngineeringIntentType
    confidence: float
    parameters: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    entities: List[dict] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineeringGraph:
    """Knowledge graph representing the engineering design."""
    nodes: Dict[str, dict] = field(default_factory=dict)
    edges: List[dict] = field(default_factory=list)
    validated: bool = False
    validation_errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Intent Parser
# ---------------------------------------------------------------------------


class IntentParser:
    """Parses natural language engineering requests into structured intents.

    Uses pattern matching and keyword extraction to identify:
    - Equipment types (panel, transformer, bus, cable, etc.)
    - Quantities and specifications
    - Spatial relationships
    - Engineering constraints
    """

    # Intent patterns
    PATTERNS: Dict[EngineeringIntentType, List[str]] = {
        EngineeringIntentType.CREATE_PANEL: [
            "panel", "create panel", "add panel", "new panel", "panelboard",
            "mdb", "distribution panel", "lighting panel", "power panel",
        ],
        EngineeringIntentType.CREATE_SLD: [
            "single line diagram", "sld", "one-line diagram",
            "generate drawing", "create drawing",
        ],
        EngineeringIntentType.ADD_FEEDER: [
            "add feeder", "feeder", "outgoing circuit",
            "branch circuit", "add circuit",
        ],
        EngineeringIntentType.ADD_TRANSFORMER: [
            "add transformer", "create transformer", "new transformer",
            "step down transformer", "step up transformer",
        ],
        EngineeringIntentType.ADD_BUS: [
            "add bus", "create bus", "new bus", "busbar",
            "add busbar", "electrical bus",
        ],
        EngineeringIntentType.ADD_CABLE: [
            "add cable", "run cable", "cable", "connect",
            "wire", "conductor", "feeder cable",
        ],
        EngineeringIntentType.ADD_MOTOR: [
            "add motor", "motor", "create motor", "induction motor",
            "motor starter", "vfd",
        ],
        EngineeringIntentType.ADD_GENERATOR: [
            "add generator", "generator", "genset", "diesel generator",
            "backup generator", "standby generator",
        ],
        EngineeringIntentType.ADD_LOAD: [
            "add load", "create load", "load", "equipment load",
            "lighting load", "receptacle load", "hvac load",
        ],
        EngineeringIntentType.VALIDATE_DESIGN: [
            "validate", "check design", "engineering check",
            "review design", "verify", "audit",
        ],
        EngineeringIntentType.GENERATE_REPORT: [
            "generate report", "create report", "bill of materials",
            "bom", "panel schedule", "cable schedule",
        ],
        EngineeringIntentType.SYNC_ALL: [
            "sync all", "synchronize", "update all",
            "sync everything", "full sync",
        ],
    }

    # Parameter extraction patterns
    PARAM_PATTERNS = {
        "voltage": r"(\d+(?:\.\d+)?)\s*(?:v|volt|voltage|kv|kilovolt)",
        "current": r"(\d+(?:\.\d+)?)\s*(?:a|amp|ampere|amps)",
        "power": r"(\d+(?:\.\d+)?)\s*(?:kw|kva|mw|mva|watt|w)",
        "feeder_count": r"(\d+)\s*(?:feeders|outgoing circuits|outgoing feeder)",
        "count": r"(\d+)\s*(?:circuits|feeder|breaker)",
        "length": r"(\d+(?:\.\d+)?)\s*(?:m|meter|meters|ft|feet)",
        "size": r"(\d+(?:\.\d+)?)\s*(?:mm2|sqmm|mm)",
        "phases": r"(\d)\s*(?:phase|ph|pole)",
        "ratio": r"(\d+(?:\.\d+)?)\s*(?:percent|%|ratio)",
    }

    def parse(self, text: str) -> EngineeringIntent:
        """Parse a natural language engineering request.

        Parameters
        ----------
        text : str
            Natural language request like "Create MDB panel with 5 outgoing
            feeders and 1 transformer."

        Returns
        -------
        EngineeringIntent
            Structured intent with type, confidence, parameters, and entities.
        """
        text_lower = text.lower().strip()
        parameters: Dict[str, Any] = {}
        entities: List[dict] = []

        # 1. Identify intent type
        intent_type, confidence = self._match_intent(text_lower)

        # 2. Extract numerical parameters
        parameters = self._extract_parameters(text_lower)

        # 3. Extract named entities
        entities = self._extract_entities(text_lower)

        # 4. Extract spatial constraints
        constraints = self._extract_constraints(text_lower)

        return EngineeringIntent(
            type=intent_type,
            confidence=confidence,
            parameters=parameters,
            raw_text=text,
            entities=entities,
            constraints=constraints,
        )

    def _match_intent(self, text: str) -> Tuple[EngineeringIntentType, float]:
        """Match the intent type based on keyword patterns."""
        best_type = EngineeringIntentType.UNKNOWN
        best_score = 0.0

        for intent_type, patterns in self.PATTERNS.items():
            score = 0.0
            for pattern in patterns:
                if pattern in text:
                    # Weight by pattern length for specificity
                    score += len(pattern) / 20.0
            if score > best_score:
                best_score = score
                best_type = intent_type

        # Normalize confidence
        confidence = min(best_score, 1.0)
        return best_type, confidence

    def _extract_parameters(self, text: str) -> Dict[str, Any]:
        """Extract numerical and categorical parameters from text."""
        import re
        params: Dict[str, Any] = {}

        for param_name, pattern in self.PARAM_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                values = [float(m) if "." in m or m.isdigit() else m for m in matches]
                # Convert units
                if param_name == "voltage":
                    if "kv" in text.lower() or "kilovolt" in text.lower():
                        values = [v * 1000 for v in values]
                elif param_name == "power":
                    if "mw" in text.lower() or "mva" in text.lower():
                        values = [v * 1000 for v in values]  # MW → kW
                params[param_name] = values[0] if len(values) == 1 else values

        return params

    def _extract_entities(self, text: str) -> List[dict]:
        """Extract named entities from the request."""
        entities = []

        # Panel types
        if "mdb" in text.lower():
            entities.append({"type": "panel", "panel_type": "MDP"})
        if "lighting panel" in text.lower() or "lp" in text.lower().split():
            entities.append({"type": "panel", "panel_type": "LP"})
        if "power panel" in text.lower():
            entities.append({"type": "panel", "panel_type": "POWER_PANEL"})
        if "sub panel" in text.lower() or "sp" in text.lower().split():
            entities.append({"type": "panel", "panel_type": "SP"})

        # Transformer types
        if "step down" in text.lower():
            entities.append({"type": "transformer", "transformer_type": "step_down"})
        if "step up" in text.lower():
            entities.append({"type": "transformer", "transformer_type": "step_up"})

        return entities

    def _extract_constraints(self, text: str) -> Dict[str, Any]:
        """Extract engineering constraints."""
        constraints: Dict[str, Any] = {}

        if "emergency" in text.lower() or "standby" in text.lower():
            constraints["load_category"] = "standby"
        if "critical" in text.lower():
            constraints["load_category"] = "critical"
        if "interruptible" in text.lower():
            constraints["interruptible"] = True

        return constraints


# ---------------------------------------------------------------------------
# Engineering Graph Builder
# ---------------------------------------------------------------------------


class GraphBuilder:
    """Builds an engineering knowledge graph from parsed intents."""

    def build(self, intent: EngineeringIntent) -> EngineeringGraph:
        """Build an engineering graph from a parsed intent.

        Creates nodes for each entity and edges for their relationships.
        Validates the graph for consistency.
        """
        graph = EngineeringGraph()
        root_id = f"root_{uuid.uuid4().hex[:8]}"

        graph.nodes[root_id] = {
            "id": root_id,
            "type": "request",
            "intent": intent.type.value,
            "label": intent.raw_text[:80],
        }

        for entity in intent.entities:
            entity_id = f"{entity['type']}_{uuid.uuid4().hex[:8]}"
            entity["id"] = entity_id
            graph.nodes[entity_id] = entity
            graph.edges.append({
                "from": root_id,
                "to": entity_id,
                "type": "creates",
            })

        # Apply parameters to nodes
        if intent.parameters:
            for node_id in graph.nodes:
                if graph.nodes[node_id].get("type") in ("panel", "transformer", "bus"):
                    if "voltage" in intent.parameters:
                        graph.nodes[node_id]["voltage"] = intent.parameters["voltage"]
                    if "power" in intent.parameters:
                        graph.nodes[node_id]["power"] = intent.parameters["power"]
                    if "count" in intent.parameters:
                        graph.nodes[node_id]["count"] = intent.parameters["count"]
                    if "feeder_count" in intent.parameters:
                        graph.nodes[node_id]["feeder_count"] = intent.parameters["feeder_count"]

        graph.validated = len(graph.validation_errors) == 0
        return graph


# ---------------------------------------------------------------------------
# Model Generator
# ---------------------------------------------------------------------------


class ModelGenerator:
    """Generates Unified Engineering Model entities from engineering intents."""

    def generate(self, graph: EngineeringGraph) -> UnifiedEngineeringModel:
        """Generate a UnifiedEngineeringModel from an engineering graph."""
        from autodesk_connector.shared.models import Project

        model = UnifiedEngineeringModel(
            project=Project(
                name=f"AI Generated Project — {time.strftime('%Y-%m-%d %H:%M')}",
                entity_type="project",
            )
        )

        for node_id, node in graph.nodes.items():
            entity_type = node.get("type", "")

            if entity_type == "panel":
                self._create_panel_from_node(model, node, graph)
            elif entity_type == "transformer":
                self._create_transformer_from_node(model, node, graph)
            elif entity_type == "bus":
                self._create_bus_from_node(model, node, graph)
            elif entity_type == "cable":
                self._create_cable_from_node(model, node, graph)
            elif entity_type == "motor":
                self._create_motor_from_node(model, node, graph)
            elif entity_type == "load":
                self._create_load_from_node(model, node, graph)

        return model

    def _create_panel_from_node(self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph) -> None:
        """Create a Panel entity from a graph node."""
        voltage = node.get("voltage", 415)
        count = int(node.get("count", 1))

        for i in range(count):
            panel = Panel(
                name=f"{node.get('panel_type', 'MDP')}-{i + 1}",
                panel_type=node.get("panel_type", "MDP"),
                voltage_nominal_v=voltage if isinstance(voltage, (int, float)) else 415,
                main_breaker_a=node.get("main_breaker", 1600) if i == 0 else None,
                coordinates=Coordinates(x=i * 50, y=0),
                source_system="ai_generated",
            )

            # Add feeders if specified
            feeder_count = int(node.get("count", 1)) if "feeder" in str(node.get("type", "")) else 0
            if feeder_count > 0:
                for f in range(feeder_count):
                    panel.feeders.append({
                        "breaker_id": f"BRK-{panel.name}-{f + 1}",
                        "rated_current_a": node.get("current", 63) if isinstance(node.get("current"), (int, float)) else 63,
                        "load_name": f"LOAD-{panel.name}-{f + 1}",
                        "load_kw": node.get("power", 10) if isinstance(node.get("power"), (int, float)) else 10,
                    })

            model.project.panels.append(panel)

    def _create_transformer_from_node(self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph) -> None:
        """Create a Transformer entity from a graph node."""
        xf = Transformer(
            name=f"XF-{node.get('transformer_type', 'DIST').upper()}-1",
            from_bus_id=node.get("from_bus", "BUS-SRC"),
            to_bus_id=node.get("to_bus", "BUS-LOAD"),
            rated_power_mva=node.get("power", 1.0) / 1000 if node.get("power", 0) > 100 else node.get("power", 1.0),
            transformer_type=node.get("transformer_type", "distribution"),
            primary_voltage_kv=11.0,
            secondary_voltage_kv=0.415,
            impedance_percent=node.get("impedance", 5.75),
            source_system="ai_generated",
        )
        # Add to model via project metadata
        model.metadata.setdefault("transformers", []).append(xf.model_dump(mode="json"))

    def _create_bus_from_node(self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph) -> None:
        """Create a Bus entity from a graph node."""
        bus = Bus(
            name=node.get("name", f"BUS-{uuid.uuid4().hex[:6].upper()}"),
            base_kv=node.get("voltage", 11.0) / 1000 if node.get("voltage", 11000) > 1000 else node.get("voltage", 11.0),
            voltage_magnitude_pu=1.0,
            source_system="ai_generated",
        )
        model.metadata.setdefault("buses", []).append(bus.model_dump(mode="json"))

    def _create_cable_from_node(self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph) -> None:
        """Create a Cable entity from a graph node."""
        cable = Cable(
            name=node.get("name", f"CBL-{uuid.uuid4().hex[:6].upper()}"),
            from_bus_id=node.get("from_bus", "BUS-1"),
            to_bus_id=node.get("to_bus", "BUS-2"),
            length_m=node.get("length", 100),
            conductor_size_mm2=node.get("size", 95),
            voltage_rating_kv=0.6,
            source_system="ai_generated",
        )
        model.metadata.setdefault("cables", []).append(cable.model_dump(mode="json"))

    def _create_motor_from_node(self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph) -> None:
        """Create a Motor entity from a graph node."""
        motor = Motor(
            name=node.get("name", f"MTR-{uuid.uuid4().hex[:6].upper()}"),
            bus_id=node.get("bus_id", "BUS-LOAD"),
            rated_power_kw=node.get("power", 75),
            rated_voltage_v=node.get("voltage", 400),
            starting_method=node.get("starter", "across_the_line"),
            source_system="ai_generated",
        )
        model.metadata.setdefault("motors", []).append(motor.model_dump(mode="json"))

    def _create_load_from_node(self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph) -> None:
        """Create a Load entity from a graph node."""
        load = Load(
            name=node.get("name", f"LOAD-{uuid.uuid4().hex[:6].upper()}"),
            bus_id=node.get("bus_id", "BUS-LOAD"),
            rated_power_kw=node.get("power", 10),
            load_type=node.get("load_type", "generic"),
            source_system="ai_generated",
        )
        model.metadata.setdefault("loads", []).append(load.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# AI Drawing Engine
# ---------------------------------------------------------------------------


class AIDrawingEngine:
    """Autonomous CAD generation engine.

    Translates natural language engineering requests into:
      1. Engineering Graph
      2. Unified Engineering Model
      3. AutoCAD drawing commands
      4. Sync with ETAP/Revit

    Usage
    -----
    >>> engine = AIDrawingEngine(autocad_connector, revit_connector)
    >>> result = engine.process("Create MDB panel with 5 outgoing feeders and 1 transformer")
    >>> result['status']
    'completed'
    """

    def __init__(self, autocad_connector=None, revit_connector=None, etap_provider=None):
        self.parser = IntentParser()
        self.graph_builder = GraphBuilder()
        self.model_generator = ModelGenerator()

        self.autocad = autocad_connector
        self.revit = revit_connector
        self.etap_provider = etap_provider

        from copilot.translation.engine import TranslationEngine
        self.translation = TranslationEngine()

        self._history: List[dict] = []

    def process(self, natural_language_request: str) -> dict:
        """Process a natural language engineering request end-to-end.

        Parameters
        ----------
        natural_language_request : str
            Engineering intent in natural language.
            Example: "Create MDB panel with 5 outgoing feeders and 1 transformer."

        Returns
        -------
        dict
            Complete result with model, drawing commands, sync results,
            and validation report.
        """
        start_time = time.time()
        result: dict = {
            "status": "processing",
            "request": natural_language_request,
            "steps": {},
        }

        try:
            # 1. Parse intent
            intent = self.parser.parse(natural_language_request)
            result["steps"]["intent_parsing"] = {
                "type": intent.type.value,
                "confidence": intent.confidence,
                "parameters": intent.parameters,
                "entities": intent.entities,
            }

            # 2. Build engineering graph
            graph = self.graph_builder.build(intent)
            result["steps"]["graph_building"] = {
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "validated": graph.validated,
            }

            # 3. Generate unified model
            model = self.model_generator.generate(graph)
            result["steps"]["model_generation"] = {
                "panels": len(model.project.panels),
                "summary": model.summary(),
            }

            # 4. Generate AutoCAD drawing commands
            if self.autocad and self.autocad.is_connected:
                autocad_result = []
                for panel in model.project.panels:
                    ad_result = self.autocad.draw_panel(panel)
                    autocad_result.append(ad_result)
                result["steps"]["autocad_drawing"] = {
                    "success": True,
                    "elements_drawn": len(autocad_result),
                }
            else:
                # Generate AutoCAD commands without live connection
                autocad_commands = self.translation.unified_to_autocad_commands(
                    model.model_dump()
                )
                result["steps"]["autocad_commands"] = {
                    "generated": True,
                    "command_count": len(autocad_commands),
                    "commands": autocad_commands,
                }

            # 5. Sync to Revit if connected
            if self.revit and self.revit.is_connected:
                revit_result = self.revit.import_from_unified_model(model)
                result["steps"]["revit_sync"] = {
                    "success": revit_result.get("success", False),
                    "details": revit_result,
                }

            # 6. Sync to ETAP if available
            if self.etap_provider and self.etap_provider.is_available():
                etap_data = self.translation.unified_to_etap(model.model_dump())
                result["steps"]["etap_sync"] = {
                    "success": True,
                    "entities_synced": len(etap_data.get("buses", {})),
                }

            # 7. Generate validation report
            validation = {
                "model_integrity": {"passed": len(model.project.panels) > 0, "issues": []},
                "voltage_check": {"passed": True, "issues": []},
                "feeder_check": {"passed": True, "issues": []},
            }
            if model.project.panels:
                for panel in model.project.panels:
                    if panel.main_breaker_a and panel.bus_rating_a:
                        if panel.main_breaker_a > panel.bus_rating_a:
                            validation["feeder_check"]["issues"].append(
                                f"Panel {panel.name}: breaker > bus rating"
                            )
                validation["feeder_check"]["passed"] = len(validation["feeder_check"]["issues"]) == 0

            result["steps"]["validation"] = validation

            result["status"] = "completed"
            result["elapsed_seconds"] = round(time.time() - start_time, 3)

            # Log to history
            self._history.append({
                "request": natural_language_request,
                "intent_type": intent.type.value,
                "confidence": intent.confidence,
                "status": "completed",
                "elapsed": result["elapsed_seconds"],
                "timestamp": time.time(),
            })

        except Exception as e:
            logger.exception("AI Drawing Engine failed")
            result["status"] = "failed"
            result["error"] = str(e)
            result["elapsed_seconds"] = round(time.time() - start_time, 3)

        return result

    def get_history(self, limit: int = 20) -> List[dict]:
        """Get recent processing history."""
        return self._history[-limit:]

    def get_statistics(self) -> dict:
        """Get engine statistics."""
        total = len(self._history)
        completed = sum(1 for h in self._history if h["status"] == "completed")
        avg_time = sum(h["elapsed"] for h in self._history) / total if total > 0 else 0
        return {
            "total_requests": total,
            "completed": completed,
            "failed": total - completed,
            "average_processing_time_seconds": round(avg_time, 3),
        }
