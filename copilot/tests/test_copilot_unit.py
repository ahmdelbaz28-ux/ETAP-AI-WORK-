"""
Engineering Copilot — Integration Tests
========================================
Tests for the unified model, translation engine, AI drawing engine,
MCP server, AutoCAD/Revit connectors, and API routes.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from autodesk_connector.shared.models import (
    Breaker,
    Bus,
    Cable,
    Coordinates,
    Generator,
    Load,
    Panel,
    Transformer,
    UnifiedEngineeringModel,
    SourceSystem,
    PanelType,
    BusType,
    TransformerType,
    LoadType,
)
from copilot.translation.engine import TranslationEngine, ENTITY_DRAWING_RULES
from copilot.ai.drawing_engine import IntentParser, GraphBuilder, ModelGenerator, AIDrawingEngine
from copilot.mcp.server import CopilotMCPServer, MCP_TOOL_DEFINITIONS


# =========================================================================
# Test: Unified Engineering Model
# =========================================================================


class TestUnifiedEngineeringModel(unittest.TestCase):
    """Test the Unified Engineering Model data models."""

    def test_create_bus(self):
        bus = Bus(
            id="BUS-001",
            name="Main Bus",
            bus_type=BusType.SLACK,
            base_kv=11.0,
            voltage_magnitude_pu=1.05,
            source_system=SourceSystem.MANUAL,
        )
        self.assertEqual(bus.id, "BUS-001")
        self.assertEqual(bus.bus_type, BusType.SLACK)
        self.assertEqual(bus.base_kv, 11.0)
        self.assertEqual(bus.voltage_magnitude_pu, 1.05)

    def test_create_transformer(self):
        xf = Transformer(
            id="XF-001",
            name="Main Transformer",
            from_bus_id="BUS-SRC",
            to_bus_id="BUS-LOAD",
            rated_power_mva=10.0,
            transformer_type=TransformerType.STEP_DOWN,
            impedance_percent=5.75,
        )
        self.assertEqual(xf.rated_power_mva, 10.0)
        self.assertEqual(xf.from_bus_id, "BUS-SRC")
        self.assertEqual(xf.to_bus_id, "BUS-LOAD")
        self.assertEqual(xf.impedance_percent, 5.75)

    def test_create_panel(self):
        panel = Panel(
            id="MDP-01",
            name="Main Distribution Panel",
            panel_type=PanelType.MDP,
            voltage_nominal_v=415,
            main_breaker_a=1600,
            bus_rating_a=2000,
            phase_count=3,
        )
        self.assertEqual(panel.panel_type, PanelType.MDP)
        self.assertEqual(panel.voltage_nominal_v, 415)
        self.assertEqual(panel.main_breaker_a, 1600)

    def test_create_cable(self):
        cable = Cable(
            id="CBL-001",
            name="Feeder Cable",
            from_bus_id="BUS-1",
            to_bus_id="BUS-2",
            length_m=150.0,
            conductor_size_mm2=95.0,
            cable_type="power",
        )
        self.assertEqual(cable.length_m, 150.0)
        self.assertEqual(cable.conductor_size_mm2, 95.0)
        self.assertEqual(cable.from_bus_id, "BUS-1")

    def test_create_breaker(self):
        breaker = Breaker(
            id="BRK-001",
            name="Main Breaker",
            rated_current_a=1600,
            interrupting_rating_ka=65,
            poles=3,
        )
        self.assertEqual(breaker.rated_current_a, 1600)
        self.assertEqual(breaker.interrupting_rating_ka, 65)

    def test_create_load(self):
        load = Load(
            id="LOAD-001",
            name="Motor Load",
            bus_id="BUS-3",
            rated_power_kw=75.0,
            load_type=LoadType.MOTOR,
            power_factor=0.85,
        )
        self.assertEqual(load.rated_power_kw, 75.0)
        self.assertEqual(load.bus_id, "BUS-3")
        self.assertEqual(load.load_type, LoadType.MOTOR)

    def test_coordinates(self):
        coord = Coordinates(x=10.0, y=20.0, z=5.0)
        self.assertEqual(coord.x, 10.0)
        self.assertEqual(coord.y, 20.0)
        self.assertEqual(coord.z, 5.0)

    def test_model_serialization_roundtrip(self):
        """Test JSON serialization and deserialization."""
        panel = Panel(
            id="PNL-1", name="Test Panel",
            panel_type=PanelType.MDP, voltage_nominal_v=415,
        )
        model = UnifiedEngineeringModel(
            project=__import__("autodesk_connector.shared.models", fromlist=["Project"]).Project(
                name="Test Project",
                entity_type="project",
            )
        )
        model.project.panels.append(panel)

        # Serialize
        json_str = model.to_json()
        self.assertIn("Test Panel", json_str)
        self.assertIn("MDP", json_str)

        # Deserialize
        restored = UnifiedEngineeringModel.from_json(json_str)
        self.assertEqual(len(restored.project.panels), 1)
        self.assertEqual(restored.project.panels[0].name, "Test Panel")
        self.assertEqual(restored.project.panels[0].panel_type, PanelType.MDP)


# =========================================================================
# Test: Translation Engine
# =========================================================================


class TestTranslationEngine(unittest.TestCase):
    """Test the CAD Translation Engine."""

    def setUp(self):
        self.engine = TranslationEngine()

    def test_get_drawing_rule(self):
        rule = self.engine.get_drawing_rule("Bus", "autocad")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.get("entity_type"), "block")
        self.assertEqual(rule.get("layer"), "E-BUS")

        rule_xf = self.engine.get_drawing_rule("Transformer", "autocad")
        self.assertEqual(rule_xf.get("entity_type"), "dynamic_block")

    def test_get_all_mapping_rules(self):
        rules = self.engine.get_all_mapping_rules()
        self.assertIn("Bus", rules)
        self.assertIn("Transformer", rules)
        self.assertIn("Cable", rules)
        self.assertIn("Breaker", rules)
        self.assertIn("Panel", rules)
        self.assertIn("Load", rules)
        self.assertIn("Motor", rules)
        self.assertIn("Generator", rules)

    def test_etap_to_unified_buses(self):
        etap_data = {
            "buses": {
                "BUS1": {"voltage_magnitude": 1.05, "voltage_angle": 0.0, "bus_type": "swing", "base_kv": 11.0},
                "BUS2": {"voltage_magnitude": 0.98, "voltage_angle": -2.5, "bus_type": "pq", "base_kv": 11.0},
            },
            "branches": {
                "BUS1-BUS2": {"active_power_from": 50.0, "active_power_to": -49.8, "current": 0.52},
            },
        }

        result = self.engine.etap_to_unified(etap_data)
        self.assertEqual(len(result["buses"]), 2)
        self.assertEqual(len(result["cables"]), 1)
        self.assertEqual(result["buses"][0]["voltage_magnitude_pu"], 1.05)

    def test_unified_to_etap(self):
        unified = {
            "buses": [{"id": "BUS1", "base_kv": 11.0, "voltage_magnitude_pu": 1.05, "bus_type": "slack"}],
            "cables": [{"from_bus_id": "BUS1", "to_bus_id": "BUS2", "length_m": 100.0}],
        }
        result = self.engine.unified_to_etap(unified)
        self.assertIn("BUS1", result["buses"])
        self.assertEqual(result["buses"]["BUS1"]["base_kv"], 11.0)

    def test_unified_to_autocad_commands(self):
        unified = {
            "buses": [{"id": "BUS1", "base_kv": 11.0, "voltage_magnitude_pu": 1.05, "bus_type": "slack"}],
            "cables": [{"id": "CBL1", "from_bus_id": "BUS1", "to_bus_id": "BUS2", "length_m": 100.0}],
            "transformers": [{"id": "XF1", "rated_power_mva": 10.0}],
        }
        commands = self.engine.unified_to_autocad_commands(unified)
        self.assertGreater(len(commands), 0)

        # Should include create_layer and draw commands
        create_layer_cmds = [c for c in commands if c["command"] == "create_layer"]
        self.assertGreater(len(create_layer_cmds), 0)

    def test_translate_dispatch(self):
        etap_data = {"buses": {"B1": {}}, "branches": {}}
        result = self.engine.translate("etap", "unified", etap_data)
        self.assertIn("buses", result)

        # ETAP to AutoCAD
        cmds = self.engine.translate("etap", "autocad", etap_data)
        self.assertIsInstance(cmds, list)


# =========================================================================
# Test: AI Drawing Engine
# =========================================================================


class TestAIDrawingEngine(unittest.TestCase):
    """Test the AI Drawing Engine components."""

    def setUp(self):
        self.parser = IntentParser()
        self.graph_builder = GraphBuilder()
        self.model_generator = ModelGenerator()
        self.engine = AIDrawingEngine()

    def test_parse_panel_intent(self):
        intent = self.parser.parse("Create MDB panel with 5 outgoing feeders and 1 transformer")
        self.assertEqual(intent.type.value, "create_panel")
        self.assertGreater(intent.confidence, 0.0)
        self.assertIn("feeder_count", intent.parameters)
        self.assertEqual(intent.parameters["feeder_count"], 5.0)

    def test_parse_sld_intent(self):
        intent = self.parser.parse("Generate single line diagram for the system")
        self.assertEqual(intent.type.value, "create_sld")

    def test_parse_validate_intent(self):
        intent = self.parser.parse("Validate the design and check for errors")
        self.assertEqual(intent.type.value, "validate_design")

    def test_parse_add_feeder(self):
        intent = self.parser.parse("Add feeder to panel MDP-01 with 200A breaker")
        self.assertEqual(intent.type.value, "add_feeder")
        self.assertIn("current", intent.parameters)

    def test_build_graph(self):
        intent = self.parser.parse("Create MDB panel with 5 outgoing feeders and 1 transformer")
        graph = self.graph_builder.build(intent)
        self.assertGreater(len(graph.nodes), 0)
        self.assertTrue(graph.validated)

    def test_generate_model(self):
        intent = self.parser.parse("Create MDB panel with 3 outgoing feeders")
        graph = self.graph_builder.build(intent)
        model = self.model_generator.generate(graph)
        self.assertIsNotNone(model)
        self.assertEqual(len(model.project.panels), 1)

    def test_engine_process_basic(self):
        result = self.engine.process("Create MDB panel with 2 outgoing feeders")
        self.assertEqual(result["status"], "completed")
        self.assertIn("steps", result)
        self.assertIn("intent_parsing", result["steps"])
        self.assertIn("model_generation", result["steps"])
        self.assertIn("validation", result["steps"])

    def test_engine_process_complex(self):
        result = self.engine.process("Add 500kVA transformer feeding main distribution panel with 6 outgoing circuits")
        self.assertEqual(result["status"], "completed")
        self.assertIn("model_generation", result["steps"])
        self.assertIn("autocad_commands", result["steps"])

    def test_engine_statistics(self):
        self.engine.process("Create MDB panel with 5 outgoing feeders and 1 transformer")
        self.engine.process("Add 500kVA step down transformer at 11/0.415 kV")
        stats = self.engine.get_statistics()
        self.assertEqual(stats["total_requests"], 2)
        self.assertGreaterEqual(stats["average_processing_time_seconds"], 0)


# =========================================================================
# Test: MCP Server
# =========================================================================


class TestCopilotMCPServer(unittest.TestCase):
    """Test the MCP Server tools."""

    def setUp(self):
        self.server = CopilotMCPServer()

    def test_list_tools(self):
        tools = self.server.list_tools()
        self.assertGreater(len(tools), 0)

        tool_names = [t["name"] for t in tools]
        self.assertIn("create_panel", tool_names)
        self.assertIn("create_transformer", tool_names)
        self.assertIn("create_bus", tool_names)
        self.assertIn("create_cable", tool_names)
        self.assertIn("generate_sld", tool_names)
        self.assertIn("validate_design", tool_names)
        self.assertIn("export_json", tool_names)

    def test_tool_has_schemas(self):
        tools = self.server.list_tools()
        for tool in tools:
            self.assertIn("name", tool)
            self.assertIn("description", tool)
            self.assertIn("inputSchema", tool)
            self.assertIn("properties", tool["inputSchema"])

    def test_tool_create_panel(self):
        result = self.server.call_tool("create_panel", {
            "name": "MDP-01",
            "panel_type": "MDP",
            "voltage_nominal_v": 415,
            "main_breaker_a": 1600,
        })
        self.assertTrue(result["success"])
        self.assertIn("panel_id", result)
        self.assertIn("panel", result)
        self.assertEqual(result["panel"]["panel_type"], "MDP")

    def test_tool_create_bus(self):
        result = self.server.call_tool("create_bus", {
            "name": "BUS-1",
            "base_kv": 11.0,
            "bus_type": "slack",
        })
        self.assertTrue(result["success"])
        self.assertIn("bus_id", result)
        self.assertEqual(result["bus"]["base_kv"], 11.0)

    def test_tool_create_transformer(self):
        result = self.server.call_tool("create_transformer", {
            "name": "XF-1",
            "from_bus_id": "BUS-SRC",
            "to_bus_id": "BUS-LOAD",
            "rated_power_mva": 10.0,
        })
        self.assertTrue(result["success"])
        self.assertEqual(result["transformer"]["rated_power_mva"], 10.0)

    def test_tool_create_cable(self):
        result = self.server.call_tool("create_cable", {
            "name": "CBL-1",
            "from_bus_id": "BUS-1",
            "to_bus_id": "BUS-2",
            "length_m": 100.0,
        })
        self.assertTrue(result["success"])
        self.assertEqual(result["cable"]["length_m"], 100.0)

    def test_tool_validate_design(self):
        result = self.server.call_tool("validate_design", {
            "check_types": ["voltage", "overcurrent"]
        })
        self.assertTrue(result["success"])
        self.assertIn("passed", result)
        self.assertIn("checks", result)

    def test_tool_export_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            result = self.server.call_tool("export_json", {
                "output_path": tmp_path,
                "pretty": True,
            })
            self.assertTrue(result["success"])
            self.assertTrue(os.path.exists(tmp_path))

            with open(tmp_path) as f:
                data = json.load(f)
            self.assertIn("project", data)
            self.assertEqual(data["schema_version"], "1.0.0")
        finally:
            os.unlink(tmp_path)

    def test_unknown_tool(self):
        result = self.server.call_tool("nonexistent_tool", {})
        self.assertFalse(result["success"])

    def test_health_check(self):
        health = self.server.health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertIn("autocad_connected", health)
        self.assertIn("revit_connected", health)
        self.assertIn("etap_available", health)
        self.assertIn("tools_count", health)


# =========================================================================
# Test: Drawing Rule Definitions
# =========================================================================


class TestDrawingRules(unittest.TestCase):
    """Test that all drawing rules are properly defined."""

    def test_entity_drawing_rules_completeness(self):
        """Verify all entity types have AutoCAD and Revit rules."""
        required_entities = [
            "Bus", "Transformer", "Cable", "Breaker", "Panel",
            "Load", "Motor", "Generator", "Switchboard", "Relay",
            "Equipment", "Conduit", "Tray",
        ]
        for entity in required_entities:
            self.assertIn(entity, ENTITY_DRAWING_RULES,
                          f"Missing drawing rule for {entity}")

    def test_autocad_rules_have_required_fields(self):
        for entity, rules in ENTITY_DRAWING_RULES.items():
            autocad_rules = rules.get("autocad", {})
            self.assertIn("entity_type", autocad_rules,
                          f"AutoCAD rule for {entity} missing entity_type")
            self.assertIn("layer", autocad_rules,
                          f"AutoCAD rule for {entity} missing layer")

    def test_revit_rules_have_family_info(self):
        for entity, rules in ENTITY_DRAWING_RULES.items():
            revit_rules = rules.get("revit", {})
            self.assertIn("family_category", revit_rules,
                          f"Revit rule for {entity} missing family_category")
            self.assertIn("parameters", revit_rules,
                          f"Revit rule for {entity} missing parameters")


# =========================================================================
# Test: ETAP Adapter
# =========================================================================


class TestETAPAdapter(unittest.TestCase):
    """Test the ETAP-to-Unified-Model adapter."""

    def setUp(self):
        from autodesk_connector.shared.models import ETAPModelAdapter
        self.adapter = ETAPModelAdapter()

    def test_bus_to_unified(self):
        etap_bus = {
            "id": "BUS1",
            "name": "Main Bus",
            "bus_type": "slack",
            "voltage_magnitude": 1.05,
            "voltage_angle": 0.0,
            "base_kv": 11.0,
            "load_mw": 0.0,
            "load_mvar": 0.0,
        }
        bus = self.adapter.bus_to_unified(etap_bus)
        self.assertEqual(bus.name, "Main Bus")
        self.assertEqual(bus.base_kv, 11.0)
        self.assertEqual(bus.voltage_magnitude_pu, 1.05)
        self.assertEqual(bus.source_system, SourceSystem.ETAP)

    def test_transformer_to_unified(self):
        etap_xf = {
            "id": "XF1",
            "name": "Main XF",
            "from_bus": "BUS-SRC",
            "to_bus": "BUS-LOAD",
            "rated_power_mva": 10.0,
            "impedance_percent": 5.75,
            "tap_ratio": 1.0,
        }
        xf = self.adapter.transformer_to_unified(etap_xf)
        self.assertEqual(xf.rated_power_mva, 10.0)
        self.assertEqual(xf.from_bus_id, "BUS-SRC")

    def test_cable_to_unified(self):
        etap_cable = {
            "id": "CBL1",
            "name": "Feeder",
            "from_bus": "BUS1",
            "to_bus": "BUS2",
            "length_m": 150.0,
            "conductor_size_mm2": 95.0,
        }
        cable = self.adapter.cable_to_unified(etap_cable)
        self.assertEqual(cable.length_m, 150.0)
        self.assertEqual(cable.conductor_size_mm2, 95.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
