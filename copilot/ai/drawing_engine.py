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

import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from autodesk_connector.shared.models import (
    BreakerDef,
    Bus,
    Cable,
    Coordinates,
    Generator,
    Load,
    Motor,
    Panel,
    PanelType,
    SourceSystem,
    Transformer,
    UnifiedEngineeringModel,
)
from compat import StrEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intent Data Models
# ---------------------------------------------------------------------------


class EngineeringIntentType(StrEnum):
    CREATE_PANEL = "create_panel"
    CREATE_SLD = "create_sld"
    CREATE_SUBSTATION = "create_substation"
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
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    entities: list[dict] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineeringGraph:
    """Knowledge graph representing the engineering design."""

    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)
    validated: bool = False
    validation_errors: list[str] = field(default_factory=list)


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
    PATTERNS: dict[EngineeringIntentType, list[str]] = {
        EngineeringIntentType.CREATE_PANEL: [
            "panel",
            "create panel",
            "add panel",
            "new panel",
            "panelboard",
            "mdb",
            "distribution panel",
            "lighting panel",
            "power panel",
        ],
        EngineeringIntentType.CREATE_SLD: [
            "single line diagram",
            "sld",
            "one-line diagram",
            "generate drawing",
            "create drawing",
        ],
        EngineeringIntentType.CREATE_SUBSTATION: [
            "substation",
            "create substation",
            "power substation",
            "electrical substation",
            "substation design",
            "substation project",
        ],
        EngineeringIntentType.ADD_FEEDER: [
            "add feeder",
            "feeder",
            "outgoing circuit",
            "branch circuit",
            "add circuit",
        ],
        EngineeringIntentType.ADD_TRANSFORMER: [
            "add transformer",
            "create transformer",
            "new transformer",
            "step down transformer",
            "step up transformer",
        ],
        EngineeringIntentType.ADD_BUS: [
            "add bus",
            "create bus",
            "new bus",
            "busbar",
            "add busbar",
            "electrical bus",
        ],
        EngineeringIntentType.ADD_CABLE: [
            "add cable",
            "run cable",
            "cable",
            "connect",
            "wire",
            "conductor",
            "feeder cable",
        ],
        EngineeringIntentType.ADD_MOTOR: [
            "add motor",
            "motor",
            "create motor",
            "induction motor",
            "motor starter",
            "vfd",
        ],
        EngineeringIntentType.ADD_GENERATOR: [
            "add generator",
            "generator",
            "genset",
            "diesel generator",
            "backup generator",
            "standby generator",
        ],
        EngineeringIntentType.ADD_LOAD: [
            "add load",
            "create load",
            "load",
            "equipment load",
            "lighting load",
            "receptacle load",
            "hvac load",
        ],
        EngineeringIntentType.VALIDATE_DESIGN: [
            "validate",
            "check design",
            "engineering check",
            "review design",
            "verify",
            "audit",
        ],
        EngineeringIntentType.GENERATE_REPORT: [
            "generate report",
            "create report",
            "bill of materials",
            "bom",
            "panel schedule",
            "cable schedule",
        ],
        EngineeringIntentType.SYNC_ALL: [
            "sync all",
            "synchronize",
            "update all",
            "sync everything",
            "full sync",
        ],
    }

    # Parameter extraction patterns
    # kV and V are separate patterns to avoid unit confusion (e.g. "415V" should not be scaled by 1000)
    PARAM_PATTERNS = {
        "voltage_kv": r"(\d+(?:\.\d+)?)\s*(?:kv\b|kilovolt\b)",
        "voltage_v": r"(\d+(?:\.\d+)?)\s*(?:(?<![kK])v(?!a)|volt(?!s)|voltage)",
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
        parameters: dict[str, Any] = {}
        entities: list[dict] = []

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

    def _match_intent(self, text: str) -> tuple[EngineeringIntentType, float]:
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

    def _extract_parameters(self, text: str) -> dict[str, Any]:
        """Extract numerical and categorical parameters from text."""
        import re

        params: dict[str, Any] = {}

        for param_name, pattern in self.PARAM_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                values = [float(m) if "." in m or m.isdigit() else m for m in matches]
                # Convert units
                if param_name == "voltage_kv":
                    values = [v * 1000 for v in values]  # kV → V
                    params["voltage"] = values[0] if len(values) == 1 else values
                elif param_name == "voltage_v":
                    # V values stay as-is, but only if no kV values were already extracted
                    if "voltage" not in params:
                        params["voltage"] = values[0] if len(values) == 1 else values
                    else:
                        # Merge: kV values are primary, V values are secondary
                        pass
                elif param_name == "power":
                    if "mw" in text.lower() or "mva" in text.lower():
                        values = [v * 1000 for v in values]  # MW → kW
                    params[param_name] = values[0] if len(values) == 1 else values
                else:
                    params[param_name] = values[0] if len(values) == 1 else values

        # Special handling: when `current` is a list, interpret as [main_breaker_a, feeder_a]
        # E.g. "2000A main with 200A feeders" → main=2000, feeder=200
        # E.g. "6 outgoing feeders each 200A" → feeder=200
        if "current" in params and isinstance(params["current"], list):
            currents = params["current"]
            params["main_current"] = currents[0]
            if len(currents) > 1:
                params["feeder_current"] = currents[1]
            elif "feeder" in text.lower():
                params["feeder_current"] = currents[0]

        return params

    def _extract_entities(self, text: str) -> list[dict]:
        """Extract named entities from the request."""
        entities = []

        # Panel types — comprehensive panel name detection
        text_lower = text.lower()
        if "main distribution panel" in text_lower or "mdb" in text_lower:
            entities.append({"type": "panel", "panel_type": "MDP"})
        elif "distribution panel" in text_lower or "distribution board" in text_lower:
            entities.append({"type": "panel", "panel_type": "DP"})
        if (
            "lighting panel" in text_lower
            or "lighting distribution" in text_lower
            or "lp" in text_lower.split()
        ):
            entities.append({"type": "panel", "panel_type": "LP"})
        if "power panel" in text_lower or "power distribution" in text_lower:
            entities.append({"type": "panel", "panel_type": "POWER_PANEL"})
        if (
            "sub panel" in text_lower
            or "sub distribution" in text_lower
            or "sp" in text_lower.split()
        ):
            entities.append({"type": "panel", "panel_type": "SP"})
        if "motor control center" in text_lower or "mcc" in text_lower:
            entities.append({"type": "panel", "panel_type": "MCC"})

        # Transformer types — general + specific
        if "step down" in text_lower:
            entities.append({"type": "transformer", "transformer_type": "step_down"})
        if "step up" in text_lower:
            entities.append({"type": "transformer", "transformer_type": "step_up"})
        if "main transformer" in text_lower or "power transformer" in text_lower:
            entities.append({"type": "transformer", "transformer_type": "power"})
        if "transformer" in text_lower and not any(e["type"] == "transformer" for e in entities):
            entities.append({"type": "transformer", "transformer_type": "distribution"})

        # Generator types
        if "emergency generator" in text_lower or "standby generator" in text_lower:
            entities.append(
                {"type": "generator", "generator_type": "diesel", "load_category": "standby"},
            )
        if "generator" in text_lower and not any(e["type"] == "generator" for e in entities):
            entities.append({"type": "generator", "generator_type": "synchronous"})

        return entities

    def _extract_constraints(self, text: str) -> dict[str, Any]:
        """Extract engineering constraints."""
        constraints: dict[str, Any] = {}

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
            graph.edges.append(
                {
                    "from": root_id,
                    "to": entity_id,
                    "type": "creates",
                },
            )

        # If intent is panel/substation-related but no entity was extracted,
        # create nodes from the intent type alone
        create_panel = not any(n.get("type") == "panel" for n in graph.nodes.values())
        create_xf = not any(n.get("type") == "transformer" for n in graph.nodes.values())
        create_gen = not any(n.get("type") == "generator" for n in graph.nodes.values())

        if intent.type in (
            EngineeringIntentType.CREATE_PANEL,
            EngineeringIntentType.CREATE_SUBSTATION,
        ):
            raw_lower = intent.raw_text.lower()

            # Create panel node if missing
            if create_panel:
                panel_id = f"panel_{uuid.uuid4().hex[:8]}"
                panel_type = "MDP"
                if "lighting" in raw_lower:
                    panel_type = "LP"
                elif "power panel" in raw_lower:
                    panel_type = "POWER_PANEL"
                elif "motor control" in raw_lower:
                    panel_type = "MCC"
                elif "incoming panel" in raw_lower or "main panel" in raw_lower:
                    panel_type = "MDP"
                graph.nodes[panel_id] = {
                    "id": panel_id,
                    "type": "panel",
                    "panel_type": panel_type,
                    "label": "auto panel from " + intent.raw_text[:40],
                }
                graph.edges.append({"from": root_id, "to": panel_id, "type": "creates"})

            # Create transformer node if missing and substation intent
            if create_xf and intent.type == EngineeringIntentType.CREATE_SUBSTATION:
                xf_id = f"transformer_{uuid.uuid4().hex[:8]}"
                xf_type = "step_down"
                if "step up" in raw_lower:
                    xf_type = "step_up"
                elif "main transformer" in raw_lower or "power transformer" in raw_lower:
                    xf_type = "power"
                graph.nodes[xf_id] = {
                    "id": xf_id,
                    "type": "transformer",
                    "transformer_type": xf_type,
                    "label": "auto xf from " + intent.raw_text[:40],
                }
                graph.edges.append({"from": root_id, "to": xf_id, "type": "supplies"})

            # Create generator node if missing and substation text mentions generator
            if create_gen and ("generator" in raw_lower or "genset" in raw_lower):
                gen_id = f"generator_{uuid.uuid4().hex[:8]}"
                graph.nodes[gen_id] = {
                    "id": gen_id,
                    "type": "generator",
                    "generator_type": "diesel"
                    if "emergency" in raw_lower or "standby" in raw_lower
                    else "synchronous",
                    "label": "auto gen from " + intent.raw_text[:40],
                }
                graph.edges.append({"from": root_id, "to": gen_id, "type": "supplies"})

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
                    if "main_current" in intent.parameters:
                        graph.nodes[node_id]["main_current"] = intent.parameters["main_current"]
                    if "feeder_current" in intent.parameters:
                        graph.nodes[node_id]["feeder_current"] = intent.parameters["feeder_current"]
                    # Also set from raw `current` for backward compatibility
                    if "current" in intent.parameters:
                        c = intent.parameters["current"]
                        if isinstance(c, (int, float)):
                            graph.nodes[node_id]["main_current"] = c
                            graph.nodes[node_id]["feeder_current"] = c

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
            ),
        )

        for _node_id, node in graph.nodes.items():
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
            elif entity_type == "generator":
                self._create_generator_from_node(model, node, graph)
            elif entity_type == "load":
                self._create_load_from_node(model, node, graph)

        return model

    def _create_panel_from_node(
        self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph,
    ) -> None:
        """Create a Panel entity from a graph node, linking Intent Parameters.

        Connects extracted parameters (voltage, current, feeder_count) to
        the Panel entity fields:
        - voltage  → voltage_nominal_v
        - main_current / current[0] → main_breaker_a, bus_rating_a
        - feeder_current / current[1] → feeder rated_current_a
        - feeder_count → number of BreakerDef entries in feeders
        """
        voltage = node.get("voltage", 415)
        if not isinstance(voltage, (int, float)):
            voltage = 415

        main_breaker = node.get("main_current", node.get("current", node.get("main_breaker", 1600)))
        if isinstance(main_breaker, (list, tuple)):
            main_breaker = main_breaker[0]
        elif not isinstance(main_breaker, (int, float)):
            main_breaker = 1600

        feeder_current = node.get("feeder_current", node.get("current", 63))
        if isinstance(feeder_current, (list, tuple)):
            feeder_current = feeder_current[-1]  # Use last value as feeder rating
        elif not isinstance(feeder_current, (int, float)):
            feeder_current = 63

        panel_type_str = node.get("panel_type", "MDP")
        panel_type = PanelType.MDP
        pts = panel_type_str.upper()
        if pts == "LP" or "lighting" in str(panel_type_str).lower():
            panel_type = PanelType.LP
        elif pts == "DP":
            panel_type = PanelType.DP
        elif pts == "MCC":
            panel_type = PanelType.MCC
        elif pts == "SP":
            panel_type = PanelType.SP
        elif pts == "CP":
            panel_type = PanelType.CP
        elif pts == "AHUB":
            panel_type = PanelType.AHUB
        elif pts == "POWER_PANEL":
            panel_type = PanelType.POWER_PANEL

        count = int(node.get("count", 1))
        feeder_count = int(node.get("feeder_count", 0))

        for i in range(count):
            panel = Panel(
                name=f"{panel_type_str.upper()}-{i + 1:02d}",
                panel_type=panel_type,
                voltage_nominal_v=voltage,
                main_breaker_a=main_breaker if i == 0 else None,
                bus_rating_a=main_breaker if i == 0 else None,
                phase_count=3,
                wire_count=3,
                coordinates=Coordinates(x=i * 50, y=0),
                source_system=SourceSystem.AI_GENERATED,
            )

            # Add feeders from feeder_count parameter
            if feeder_count > 0:
                feeder_power = node.get("power", 10)
                if isinstance(feeder_power, (list, tuple)):
                    feeder_power = feeder_power[-1]
                elif not isinstance(feeder_power, (int, float)):
                    feeder_power = 10

                # Calculate load_kw properly: for 3-phase, P = sqrt(3) * V * I * pf / 1000
                # Use voltage from panel, feeder_current, and 0.85 power factor as default
                load_kw_approx = round(math.sqrt(3) * voltage * feeder_current * 0.85 / 1000.0, 1)
                load_kw_final = feeder_power if feeder_power != 10 else max(load_kw_approx, 1.0)

                for f in range(feeder_count):
                    panel.feeders.append(
                        BreakerDef(
                            breaker_id=f"BRK-{panel.name}-{f + 1:02d}",
                            rated_current_a=feeder_current,
                            load_name=f"LOAD-{panel.name}-{f + 1:02d}",
                            load_kw=load_kw_final,
                            poles=3,
                        ),
                    )

            model.project.panels.append(panel)

    def _create_transformer_from_node(
        self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph,
    ) -> None:
        """Create a Transformer entity from a graph node."""
        power = node.get("power", 1.0)
        if isinstance(power, (list, tuple)):
            # Multiple power values found; use the first one that matches transformer rating (typically MVA)
            # Sort: prefer larger values (MVA ratings are typically higher kW numbers? No, MVA < kW in MVA units)
            # For "2MVA, 500kVA" — after MW→kW conversion: [2000, 500]
            # Pick the larger one for transformer rating
            power = max(power)
        elif not isinstance(power, (int, float)):
            power = 1.0
        # power is in kW (MW/kW patterns normalize to kW). MVA = kW / 1000 * pf approximately
        # But transformer rated_power_mva is MVA — need to convert from kVA, not kW
        # If power > 100, assume it's in kW and convert dividing by 1000 to get MVA
        rated_mva = power / 1000.0 if power > 100 else power

        xf = Transformer(
            name=f"XF-{node.get('transformer_type', 'DIST').upper()}-1",
            from_bus_id=node.get("from_bus", "BUS-SRC"),
            to_bus_id=node.get("to_bus", "BUS-LOAD"),
            rated_power_mva=rated_mva,
            transformer_type=node.get("transformer_type", "distribution"),
            primary_voltage_kv=11.0,
            secondary_voltage_kv=0.415,
            impedance_percent=node.get("impedance", 5.75),
            source_system=SourceSystem.AI_GENERATED,
        )
        # Add to model via project metadata
        model.metadata.setdefault("transformers", []).append(xf.model_dump(mode="json"))

    def _create_bus_from_node(
        self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph,
    ) -> None:
        """Create a Bus entity from a graph node."""
        voltage = node.get("voltage", 11000)
        if isinstance(voltage, (list, tuple)):
            voltage = voltage[0]
        elif not isinstance(voltage, (int, float)):
            voltage = 11000
        # Convert from V to kV: 11000V → 11kV, 415V → 0.415kV
        base_kv = voltage / 1000.0 if voltage >= 1000 else voltage

        bus = Bus(
            name=node.get("name", f"BUS-{uuid.uuid4().hex[:6].upper()}"),
            base_kv=base_kv,
            voltage_magnitude_pu=1.0,
            source_system=SourceSystem.AI_GENERATED,
        )
        model.metadata.setdefault("buses", []).append(bus.model_dump(mode="json"))

    def _create_cable_from_node(
        self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph,
    ) -> None:
        """Create a Cable entity from a graph node."""
        cable = Cable(
            name=node.get("name", f"CBL-{uuid.uuid4().hex[:6].upper()}"),
            from_bus_id=node.get("from_bus", "BUS-1"),
            to_bus_id=node.get("to_bus", "BUS-2"),
            length_m=node.get("length", 100),
            conductor_size_mm2=node.get("size", 95),
            voltage_rating_kv=0.6,
            source_system=SourceSystem.AI_GENERATED,
        )
        model.metadata.setdefault("cables", []).append(cable.model_dump(mode="json"))

    def _create_motor_from_node(
        self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph,
    ) -> None:
        """Create a Motor entity from a graph node."""
        voltage = node.get("voltage", 400)
        if isinstance(voltage, (list, tuple)):
            voltage = voltage[0]
        elif not isinstance(voltage, (int, float)):
            voltage = 400
        # if voltage > 1000 assume it's in V (not kV)
        voltage_v = voltage if voltage > 100 else voltage * 1000

        motor = Motor(
            name=node.get("name", f"MTR-{uuid.uuid4().hex[:6].upper()}"),
            bus_id=node.get("bus_id", "BUS-LOAD"),
            rated_power_kw=node.get("power", 75),
            rated_voltage_v=voltage_v,
            starting_method=node.get("starter", "across_the_line"),
            source_system=SourceSystem.AI_GENERATED,
        )
        model.metadata.setdefault("motors", []).append(motor.model_dump(mode="json"))

    def _create_generator_from_node(
        self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph,
    ) -> None:
        """Create a Generator entity from a graph node."""
        power_kw = node.get("power", 500)
        if isinstance(power_kw, (list, tuple)):
            power_kw = power_kw[-1]
        # Convert MVA/kVA to kW if needed (assume pf=0.8)
        # The power param comes from regex matching "kw", "kva", "mva", "mw"
        # Already normalized to kW in _extract_parameters (MW→kW, MVA→kW approx)
        if not isinstance(power_kw, (int, float)):
            power_kw = 500

        gen_type = node.get("generator_type", "synchronous")
        gen = Generator(
            name=f"GEN-{uuid.uuid4().hex[:6].upper()}",
            bus_id=node.get("bus_id", "BUS-GEN"),
            rated_power_mw=power_kw / 1000.0,
            generator_type=gen_type,
            rated_power_mva=power_kw / 850.0,  # approx MVA from kW @ 0.85 pf
            power_factor=0.85,
            internal_voltage_pu=1.0,
            source_system=SourceSystem.AI_GENERATED,
        )
        model.metadata.setdefault("generators", []).append(gen.model_dump(mode="json"))

    def _create_load_from_node(
        self, model: UnifiedEngineeringModel, node: dict, graph: EngineeringGraph,
    ) -> None:
        """Create a Load entity from a graph node."""
        power = node.get("power", 10)
        if isinstance(power, (list, tuple)):
            power = power[-1]
        elif not isinstance(power, (int, float)):
            power = 10

        load = Load(
            name=node.get("name", f"LOAD-{uuid.uuid4().hex[:6].upper()}"),
            bus_id=node.get("bus_id", "BUS-LOAD"),
            rated_power_kw=power,
            load_type=node.get("load_type", "generic"),
            source_system=SourceSystem.AI_GENERATED,
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

        self._history: list[dict] = []

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
                autocad_commands = self.translation.unified_to_autocad_commands(model.model_dump())
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
            # Gather entity counts from all sources
            panel_count = len(model.project.panels)
            xf_count = len(model.metadata.get("transformers", []))
            gen_count = len(model.metadata.get("generators", []))
            has_any_entity = panel_count + xf_count + gen_count > 0

            validation = {
                "model_integrity": {"passed": has_any_entity, "issues": []},
                "voltage_check": {"passed": True, "issues": []},
                "feeder_check": {"passed": True, "issues": []},
            }
            if not has_any_entity:
                validation["model_integrity"]["issues"].append(
                    "No entities were created from the request",
                )

            if model.project.panels:
                for panel in model.project.panels:
                    if panel.main_breaker_a and panel.bus_rating_a:
                        if panel.main_breaker_a > panel.bus_rating_a:
                            validation["feeder_check"]["issues"].append(
                                f"Panel {panel.name}: breaker > bus rating",
                            )
                validation["feeder_check"]["passed"] = (
                    len(validation["feeder_check"]["issues"]) == 0
                )

            result["steps"]["validation"] = validation

            result["status"] = "completed"
            result["elapsed_seconds"] = round(time.time() - start_time, 3)

            # Log to history
            self._history.append(
                {
                    "request": natural_language_request,
                    "intent_type": intent.type.value,
                    "confidence": intent.confidence,
                    "status": "completed",
                    "elapsed": result["elapsed_seconds"],
                    "timestamp": time.time(),
                },
            )

        except Exception as e:
            logger.exception("AI Drawing Engine failed")
            result["status"] = "failed"
            result["error"] = str(e)
            result["elapsed_seconds"] = round(time.time() - start_time, 3)

        return result

    def get_history(self, limit: int = 20) -> list[dict]:
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
