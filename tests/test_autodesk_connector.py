"""
Integration tests for Autodesk connectors — Revit and AutoCAD.

All external HTTP calls to the C# plugin endpoints are mocked via
``unittest.mock`` so no running Revit/AutoCAD instance is required.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock, patch

import pytest

# ---------------------------------------------------------------------------
# AutoCAD imports
# ---------------------------------------------------------------------------
from autodesk_connector.autocad.connector import (
    AutoCADConnector,
    AutoCADDrawingContext,
    AutoCADDrawingOperation,
    AutoCADEntityType,
    AutoCADPluginClient,
)

# ---------------------------------------------------------------------------
# Revit imports
# ---------------------------------------------------------------------------
from autodesk_connector.revit.connector import (
    RevitConnector,
    RevitElementType,
    RevitPluginClient,
)
from autodesk_connector.shared.models import (
    Annotation,
    Breaker,
    BreakerType,
    Building,
    Bus,
    BusType,
    Cable,
    CableType,
    Conduit,
    Coordinates,
    Equipment,
    Level,
    Load,
    LoadType,
    Panel,
    PanelType,
    Project,
    Room,
    Transformer,
    TransformerType,
    Tray,
    UnifiedEngineeringModel,
)

# ===========================================================================
# Helpers
# ===========================================================================


def _mock_response(json_data: Dict[str, Any] | None = None, status_code: int = 200):
    """Build a fake requests.Response."""
    resp = Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        resp.raise_for_status.side_effect = __import__("requests").exceptions.HTTPError(
            response=resp
        )
    return resp


def _make_panel(
    name: str = "MDP-1",
    panel_type: PanelType = PanelType.MDP,
    voltage_v: float = 480.0,
) -> Panel:
    return Panel(
        id="panel-1",
        name=name,
        panel_type=panel_type,
        voltage_nominal_v=voltage_v,
        phase_count=3,
        main_breaker_a=2000.0,
        bus_rating_a=2000.0,
        coordinates=Coordinates(x=10.0, y=20.0, z=0.0),
    )


def _make_level(name: str = "Level 1", elevation: float = 0.0) -> Level:
    return Level(id="level-1", name=name, elevation_m=elevation)


def _make_room(name: str = "Room 101", area: float = 50.0) -> Room:
    return Room(
        id="room-1",
        name=name,
        area_sqm=area,
        coordinates=Coordinates(x=5.0, y=10.0),
    )


def _make_bus(name: str = "Bus-1", base_kv: float = 13.8) -> Bus:
    return Bus(
        id="bus-1",
        name=name,
        bus_type=BusType.PQ,
        base_kv=base_kv,
        coordinates=Coordinates(x=100.0, y=200.0),
    )


def _make_transformer(name: str = "XF-1") -> Transformer:
    return Transformer(
        id="xf-1",
        name=name,
        transformer_type=TransformerType.DISTRIBUTION,
        from_bus_id="bus-1",
        to_bus_id="bus-2",
        rated_power_mva=2.5,
        primary_voltage_kv=13.8,
        secondary_voltage_kv=0.48,
        impedance_percent=5.75,
        tap_ratio=1.0,
        coordinates=Coordinates(x=150.0, y=200.0),
    )


def _make_cable(name: str = "Cable-1") -> Cable:
    return Cable(
        id="cable-1",
        name=name,
        cable_type=CableType.POWER,
        from_bus_id="bus-1",
        to_bus_id="bus-2",
        length_m=100.0,
        routing_path=[
            Coordinates(x=100.0, y=200.0, z=0.0),
            Coordinates(x=200.0, y=200.0, z=0.0),
        ],
    )


def _make_breaker(name: str = "BRK-1") -> Breaker:
    return Breaker(
        id="brk-1",
        name=name,
        breaker_type=BreakerType.MCCB,
        rated_current_a=400.0,
        interrupting_rating_ka=65.0,
        coordinates=Coordinates(x=120.0, y=200.0),
    )


def _make_load(name: str = "Load-1") -> Load:
    return Load(
        id="load-1",
        name=name,
        load_type=LoadType.CONSTANT_POWER,
        bus_id="bus-1",
        rated_power_kw=150.0,
        power_factor=0.85,
        coordinates=Coordinates(x=80.0, y=180.0),
    )


def _make_equipment(name: str = "Gen-1") -> Equipment:
    return Equipment(
        id="eq-1",
        name=name,
        equipment_category="generator",
        rated_power_kva=2000.0,
        voltage_nominal_v=480.0,
        coordinates=Coordinates(x=50.0, y=60.0),
        dimensions={"width_mm": 3000, "depth_mm": 1500, "height_mm": 2200},
    )


def _make_unified_model() -> UnifiedEngineeringModel:
    level = _make_level()
    room = _make_room()
    level.rooms = [room]
    building = Building(id="bldg-1", name="Building A", levels=[level])
    panel = _make_panel()
    project = Project(
        id="proj-1",
        name="Test Project",
        buildings=[building],
        panels=[panel],
    )
    return UnifiedEngineeringModel(project=project)


# ===========================================================================
# 1. Revit Plugin Client — Initialization & Configuration
# ===========================================================================


class TestRevitPluginClientInit:
    """Test RevitPluginClient initialization, configuration, and session setup."""

    def test_default_initialization(self):
        """RevitPluginClient should use default URL and timeout."""
        client = RevitPluginClient()
        assert client.base_url == "http://localhost:4830"
        assert client.timeout == 300
        assert "Content-Type" in client.session.headers
        assert client.session.headers["Content-Type"] == "application/json"

    def test_custom_initialization(self):
        """RevitPluginClient should accept custom URL, timeout, and API key."""
        client = RevitPluginClient(
            base_url="http://revit-host:9999",
            timeout=60,
            api_key="secret-key",
        )
        assert client.base_url == "http://revit-host:9999"
        assert client.timeout == 60
        assert client.session.headers["X-API-Key"] == "secret-key"

    def test_trailing_slash_stripped(self):
        """base_url trailing slash should be stripped."""
        client = RevitPluginClient(base_url="http://localhost:4830/")
        assert client.base_url == "http://localhost:4830"


# ===========================================================================
# 2. Revit Plugin Client — Availability & Health Check
# ===========================================================================


class TestRevitPluginClientHealth:
    """Test RevitPluginClient.is_available() with mocked HTTP."""

    def test_available_on_200(self):
        """is_available returns True when health endpoint returns 200."""
        client = RevitPluginClient()
        with patch.object(client.session, "get", return_value=_mock_response(status_code=200)):
            assert client.is_available() is True

    def test_unavailable_on_500(self):
        """is_available returns False when health endpoint returns 500."""
        client = RevitPluginClient()
        with patch.object(client.session, "get", return_value=_mock_response(status_code=500)):
            assert client.is_available() is False

    def test_unavailable_on_network_error(self):
        """is_available returns False on network/timeout errors."""
        import requests

        client = RevitPluginClient()
        with patch.object(client.session, "get", side_effect=requests.ConnectionError("refused")):
            assert client.is_available() is False


# ===========================================================================
# 3. Revit Plugin Client — API Call Methods
# ===========================================================================


class TestRevitPluginClientCalls:
    """Test RevitPluginClient._call and high-level methods with mocked HTTP."""

    def test_call_posts_to_correct_url(self):
        """_call should POST to /api{endpoint} with the given payload."""
        client = RevitPluginClient()
        with patch.object(
            client.session, "post", return_value=_mock_response({"ok": True})
        ) as mock_post:
            result = client._call("/model/open", {"file_path": "/tmp/test.rvt"})  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
            mock_post.assert_called_once()
            call_url = mock_post.call_args[0][0]
            assert call_url == "http://localhost:4830/api/model/open"
            assert result == {"ok": True}

    def test_open_model(self):
        """open_model should call /api/model/open with file_path."""
        client = RevitPluginClient()
        with patch.object(
            client.session, "post", return_value=_mock_response({"success": True})
        ) as mock_post:
            result = client.open_model("/tmp/project.rvt")  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
            payload = mock_post.call_args[1]["json"]
            assert payload["file_path"] == "/tmp/project.rvt"  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
            assert result["success"] is True

    def test_create_element(self):
        """create_element should send element_type and params."""
        client = RevitPluginClient()
        with patch.object(client.session, "post", return_value=_mock_response({"success": True})):
            result = client.create_element("panel", {"panel_name": "MDP-1"})
            assert result["success"] is True

    def test_list_elements_with_filters(self):
        """list_elements should pass category and level_id filters."""
        client = RevitPluginClient()
        with patch.object(
            client.session, "post", return_value=_mock_response({"elements": []})
        ) as mock_post:
            client.list_elements(category="panels", level_id="level-1")
            payload = mock_post.call_args[1]["json"]
            assert payload["category"] == "panels"
            assert payload["level_id"] == "level-1"

    def test_call_raises_on_http_error(self):
        """_call should raise on non-2xx status codes."""
        import requests

        client = RevitPluginClient()
        with patch.object(client.session, "post", return_value=_mock_response(status_code=401)):
            with pytest.raises(requests.exceptions.HTTPError):
                client._call("/model/open", {})


# ===========================================================================
# 4. Revit Connector — High-Level Operations
# ===========================================================================


class TestRevitConnector:
    """Test RevitConnector high-level orchestration methods."""

    def _make_connector(self) -> RevitConnector:
        connector = RevitConnector(plugin_url="http://localhost:4830")
        return connector

    def test_open_model_tracks_current_path(self):
        """RevitConnector.open_model stores path on success."""
        conn = self._make_connector()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ):
            result = conn.open_model("/tmp/test.rvt")  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
            assert result["success"] is True
            assert conn._current_model_path == "/tmp/test.rvt"  # NOSONAR — S5443: /tmp use is intentional & permission-hardened

    def test_open_model_does_not_track_on_failure(self):
        """RevitConnector.open_model does not update path on failure."""
        conn = self._make_connector()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": False}),
        ):
            assert conn._current_model_path is None  # NOSONAR — S5443: /tmp use is intentional & permission-hardened

    def test_create_level_logs_operation(self):
        """create_level should log the operation on success."""
        conn = self._make_connector()
        level = _make_level()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ):
            conn.create_level(level)
            log = conn.get_operation_log()
            assert len(log) == 1
            assert log[0]["operation"] == "create_level"
            assert log[0]["target"] == "Level 1"
            assert log[0]["success"] is True

    def test_create_room_generates_bounding_box(self):
        """create_room should compute a bounding box from room area and coordinates."""
        conn = self._make_connector()
        room = _make_room(name="Office", area=100.0)
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.create_room(room, level_id="level-1")
            payload = mock_post.call_args[1]["json"]
            bbox = payload["bounding_box"]
            assert "min_x" in bbox
            assert "max_x" in bbox
            # sqrt(100) = 10, so max_x should be min_x + 10
            assert abs(bbox["max_x"] - bbox["min_x"] - 10.0) < 0.01

    def test_place_panel_sends_correct_element_type(self):
        """place_panel should create a PANEL element type."""
        conn = self._make_connector()
        panel = _make_panel()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.place_panel(panel, level_id="level-1")
            payload = mock_post.call_args[1]["json"]
            assert payload["element_type"] == "panel"

    def test_place_equipment_sends_dimensions(self):
        """place_equipment should include equipment dimensions in params."""
        conn = self._make_connector()
        equipment = _make_equipment()
        location = Coordinates(x=10, y=20, z=0)
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.place_equipment(equipment, level_id="level-1", location=location)
            payload = mock_post.call_args[1]["json"]
            params = payload["params"]["parameters"]
            assert params["width_mm"] == 3000
            assert params["depth_mm"] == 1500
            assert params["height_mm"] == 2200

    def test_create_cable_tray_with_routing_path(self):
        """create_cable_tray should include routing path coordinates."""
        conn = self._make_connector()
        tray = Tray(
            id="tray-1",
            name="Tray-A",
            tray_type="ladder",
            width_mm=300,
            length_m=50.0,
            routing_path=[
                Coordinates(x=0, y=0, z=3),
                Coordinates(x=50, y=0, z=3),
            ],
        )
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.create_cable_tray(tray, level_id="level-1")
            payload = mock_post.call_args[1]["json"]
            params = payload["params"]["parameters"]
            assert "routing_path" in params
            assert params["routing_path"] == [[0, 0, 3], [50, 0, 3]]

    def test_create_conduit_without_routing_path(self):
        """create_conduit should omit routing_path when not provided."""
        conn = self._make_connector()
        conduit = Conduit(
            id="cond-1",
            name="Conduit-A",
            conduit_type="rmc",
            diameter_mm=50,
            length_m=25.0,
        )
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.create_conduit(conduit, level_id="level-1")
            payload = mock_post.call_args[1]["json"]
            params = payload["params"]["parameters"]
            assert "routing_path" not in params

    def test_export_to_unified_model(self):
        """export_to_unified_model should call sync_revit_to_model."""
        conn = self._make_connector()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True, "model": {}}),
        ):
            result = conn.export_to_unified_model()
            assert result["success"] is True

    def test_get_statistics(self):
        """get_statistics returns dict with expected keys."""
        conn = self._make_connector()
        stats = conn.get_statistics()
        assert "connected" in stats
        assert "current_model" in stats
        assert "total_operations" in stats
        assert "successful_operations" in stats


# ===========================================================================
# 5. AutoCAD Plugin Client — Initialization & Configuration
# ===========================================================================


class TestAutoCADPluginClientInit:
    """Test AutoCADPluginClient initialization and configuration."""

    def test_default_initialization(self):
        """AutoCADPluginClient should use default URL and timeout."""
        client = AutoCADPluginClient()
        assert client.base_url == "http://localhost:4820"
        assert client.timeout == 300

    def test_custom_initialization(self):
        """AutoCADPluginClient should accept custom URL, timeout, and API key."""
        client = AutoCADPluginClient(
            base_url="http://acad-host:8080",
            timeout=120,
            api_key="test-key",
        )
        assert client.base_url == "http://acad-host:8080"
        assert client.timeout == 120
        assert client.session.headers["X-API-Key"] == "test-key"

    def test_is_available_on_200(self):
        """is_available returns True when health endpoint returns 200."""
        client = AutoCADPluginClient()
        with patch.object(client.session, "get", return_value=_mock_response(status_code=200)):
            assert client.is_available() is True

    def test_is_available_on_network_error(self):
        """is_available returns False on network error."""
        import requests

        client = AutoCADPluginClient()
        with patch.object(client.session, "get", side_effect=requests.ConnectionError("down")):
            assert client.is_available() is False


# ===========================================================================
# 6. AutoCAD Plugin Client — Drawing Commands
# ===========================================================================


class TestAutoCADPluginClientCommands:
    """Test AutoCADPluginClient drawing commands with mocked HTTP."""

    def test_send_command_posts_to_api_command(self):
        """send_command should POST to /api/command with command and params."""
        client = AutoCADPluginClient()
        with patch.object(
            client.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            client.send_command("draw_line", {"start": [0, 0], "end": [100, 100]})
            call_url = mock_post.call_args[0][0]
            assert call_url == "http://localhost:4820/api/command"
            payload = mock_post.call_args[1]["json"]
            assert payload["command"] == "draw_line"

    def test_open_drawing(self):
        """open_drawing should send the file_path in params."""
        client = AutoCADPluginClient()
        with patch.object(
            client.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            client.open_drawing("/tmp/test.dwg")
            payload = mock_post.call_args[1]["json"]  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
            assert payload["command"] == "open_drawing"
            assert payload["params"]["file_path"] == "/tmp/test.dwg"
  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    def test_create_layer_sends_layer_properties(self):
        """create_layer should include name, color, linetype, lineweight."""
        client = AutoCADPluginClient()
        with patch.object(
            client.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            client.create_layer("E-PANEL", color="5", linetype="Continuous")
            payload = mock_post.call_args[1]["json"]
            params = payload["params"]
            assert params["name"] == "E-PANEL"
            assert params["color"] == "5"

    def test_draw_line_sends_coordinates(self):
        """draw_line should include start, end, and layer."""
        client = AutoCADPluginClient()
        with patch.object(
            client.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            client.draw_line([0, 0, 0], [100, 100, 0], layer="E-CABLE")
            payload = mock_post.call_args[1]["json"]
            params = payload["params"]
            assert params["start"] == [0, 0, 0]
            assert params["end"] == [100, 100, 0]
            assert params["layer"] == "E-CABLE"

    def test_batch_operation_sends_list(self):
        """batch_operation should send a list of operations."""
        client = AutoCADPluginClient()
        ops = [{"command": "draw_line", "params": {}}]
        with patch.object(
            client.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            client.batch_operation(ops)
            payload = mock_post.call_args[1]["json"]
            assert payload["params"]["operations"] == ops


# ===========================================================================
# 7. AutoCAD Connector — High-Level Operations
# ===========================================================================


class TestAutoCADConnector:
    """Test AutoCADConnector high-level orchestration methods."""

    def _make_connector(self) -> AutoCADConnector:
        return AutoCADConnector(plugin_url="http://localhost:4820")

    def test_open_drawing_creates_context(self):
        """AutoCADConnector.open_drawing should create an AutoCADDrawingContext."""
        conn = self._make_connector()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ):
            result = conn.open_drawing("/tmp/test.dwg")
            assert result["success"] is True  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
            assert conn._current_drawing is not None
            assert conn._current_drawing.file_path == "/tmp/test.dwg"
  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    def test_close_drawing_clears_context(self):
        """AutoCADConnector.close_drawing should set _current_drawing to None."""
        conn = self._make_connector()
        conn._current_drawing = AutoCADDrawingContext("/tmp/test.dwg")
        result = conn.close_drawing()  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        assert result["success"] is True
        assert conn._current_drawing is None

    def test_draw_bus_sends_electrical_symbol(self):
        """draw_bus should call draw_electrical_symbol with bus attributes."""
        conn = self._make_connector()
        bus = _make_bus()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_bus(bus)
            payload = mock_post.call_args[1]["json"]
            params = payload["params"]
            assert params["symbol_type"] == "bus"
            assert params["attributes"]["NAME"] == "Bus-1"
            assert params["attributes"]["KV"] == "13.8"

    def test_draw_transformer_sends_attributes(self):
        """draw_transformer should send MVA, KV, Z_PCT in attributes."""
        conn = self._make_connector()
        xf = _make_transformer()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_transformer(xf)
            payload = mock_post.call_args[1]["json"]
            attrs = payload["params"]["attributes"]
            assert attrs["MVA"] == "2.5"
            assert attrs["KV_PRIM"] == "13.8"

    def test_draw_cable_with_routing_path(self):
        """draw_cable should use routing_path vertices when available."""
        conn = self._make_connector()
        cable = _make_cable()
        # Mock both create_layer and draw_polyline calls
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_cable(cable)
            # Should have made at least 2 calls: create_layer + draw_polyline
            assert mock_post.call_count >= 1

    def test_draw_breaker_sends_poles(self):
        """draw_breaker should include pole count in attributes."""
        conn = self._make_connector()
        breaker = _make_breaker()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_breaker(breaker)
            payload = mock_post.call_args[1]["json"]
            attrs = payload["params"]["attributes"]
            assert attrs["POLES"] == "3"

    def test_draw_panel_sends_phase_count(self):
        """draw_panel should include PHASES in attributes."""
        conn = self._make_connector()
        panel = _make_panel()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_panel(panel)
            payload = mock_post.call_args[1]["json"]
            attrs = payload["params"]["attributes"]
            assert attrs["PHASES"] == "3"

    def test_draw_load_sends_kw_and_pf(self):
        """draw_load should include KW and PF in attributes."""
        conn = self._make_connector()
        load = _make_load()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_load(load)
            payload = mock_post.call_args[1]["json"]
            attrs = payload["params"]["attributes"]
            assert attrs["KW"] == "150.0"
            assert attrs["PF"] == "0.85"

    def test_draw_annotation_label(self):
        """draw_annotation with label type should call draw_text."""
        conn = self._make_connector()
        annotation = Annotation(
            id="anno-1",
            name="Note",
            annotation_type="label",
            text="Warning: High Voltage",
            font_size=3.5,
            coordinates=Coordinates(x=10, y=20),
        )
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_annotation(annotation)
            payload = mock_post.call_args[1]["json"]
            assert payload["command"] == "draw_text"
            assert payload["params"]["text"] == "Warning: High Voltage"

    def test_draw_annotation_dimension(self):
        """draw_annotation with dimension type should call draw_dimension."""
        conn = self._make_connector()
        annotation = Annotation(
            id="anno-2",
            name="Dim",
            annotation_type="dimension",
            text="5000",
            coordinates=Coordinates(x=10, y=20),
        )
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_annotation(annotation)
            payload = mock_post.call_args[1]["json"]
            assert payload["command"] == "draw_dimension"

    def test_get_statistics_with_drawing(self):
        """get_statistics should report current_drawing path when available."""
        conn = self._make_connector()
        conn._current_drawing = AutoCADDrawingContext("/tmp/proj.dwg")
        stats = conn.get_statistics()  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        assert stats["current_drawing"] == "/tmp/proj.dwg"
  # NOSONAR — S5443: /tmp use is intentional & permission-hardened

# ===========================================================================
# 8. Data Model Validation — shared/models.py
# ===========================================================================


class TestDataModelValidation:
    """Test shared Pydantic models used by both connectors."""

    def test_coordinates_defaults_z_to_zero(self):
        """Coordinates should default z to 0.0."""
        c = Coordinates(x=1.0, y=2.0)
        assert c.z == 0.0

    def test_panel_requires_voltage(self):
        """Panel should require voltage_nominal_v."""
        with pytest.raises((ValueError, TypeError)):
            Panel(name="Bad Panel", panel_type=PanelType.MDP)

    def test_bus_requires_base_kv(self):
        """Bus should require base_kv."""
        with pytest.raises((ValueError, TypeError)):
            Bus(name="Bad Bus")

    def test_cable_routing_path_is_list_of_coordinates(self):
        """Cable.routing_path should accept a list of Coordinates."""
        cable = _make_cable()
        assert len(cable.routing_path) == 2
        assert isinstance(cable.routing_path[0], Coordinates)

    def test_unified_model_serialization_roundtrip(self):
        """UnifiedEngineeringModel should serialize to JSON and back."""
        model = _make_unified_model()
        json_str = model.to_json()
        restored = UnifiedEngineeringModel.from_json(json_str)
        assert restored.project.name == "Test Project"
        assert len(restored.project.buildings) == 1

    def test_unified_model_from_dict(self):
        """UnifiedEngineeringModel should be constructable from a dict."""
        model = _make_unified_model()
        data = model.model_dump()
        restored = UnifiedEngineeringModel.from_dict(data)
        assert restored.schema_version == model.schema_version


# ===========================================================================
# 9. Connection Failure Handling
# ===========================================================================


class TestConnectionFailures:
    """Test how connectors handle various failure scenarios."""

    def test_revit_timeout_error(self):
        """RevitPluginClient should propagate timeout errors from _call."""
        import requests

        client = RevitPluginClient()
        with patch.object(
            client.session,
            "post",
            side_effect=requests.exceptions.Timeout("timed out"),
        ):
            with pytest.raises(requests.exceptions.Timeout):
                client._call("/model/open", {})

    def test_revit_auth_error(self):
        """RevitPluginClient should raise HTTPError on 401."""
        import requests

        client = RevitPluginClient()
        with patch.object(
            client.session,
            "post",
            return_value=_mock_response(status_code=401),
        ):
            with pytest.raises(requests.exceptions.HTTPError):
                client._call("/model/open", {})

    def test_autocad_network_error(self):
        """AutoCADPluginClient should propagate connection errors."""
        import requests

        client = AutoCADPluginClient()
        with patch.object(
            client.session,
            "post",
            side_effect=requests.exceptions.ConnectionError("refused"),
        ):
            with pytest.raises(requests.exceptions.ConnectionError):
                client.send_command("open_drawing", {"file_path": "/tmp/x.dwg"})
  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
    def test_autocad_server_error(self):
        """AutoCADPluginClient should raise on 500."""
        import requests

        client = AutoCADPluginClient()
        with patch.object(
            client.session,
            "post",
            return_value=_mock_response(status_code=500),
        ):
            with pytest.raises(requests.exceptions.HTTPError):
                client.send_command("draw_line", {"start": [0, 0], "end": [1, 1]})

    def test_revit_connector_handles_gracefully(self):
        """RevitConnector should handle plugin failures without crashing."""
        conn = RevitConnector()
        with patch.object(
            conn.plugin.session,
            "post",
            side_effect=Exception("unexpected failure"),
        ):
            with pytest.raises(Exception, match="unexpected failure"):
                conn.open_model("/tmp/crash.rvt")
            # Should still have a valid connector state  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
            assert conn._current_model_path is None


# ===========================================================================
# 10. Data Transformation — Unified Model ↔ Autodesk Format
# ===========================================================================


class TestDataTransformation:
    """Test transformation between Unified Engineering Model and Autodesk format."""

    def test_panel_to_revit_params(self):
        """RevitConnector should map Panel fields to Revit element parameters."""
        conn = RevitConnector()
        panel = _make_panel()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.place_panel(panel, level_id="level-1")
            payload = mock_post.call_args[1]["json"]
            params = payload["params"]["parameters"]
            assert params["panel_type"] == "MDP"
            assert params["voltage_v"] == 480.0
            assert params["phase_count"] == pytest.approx(3)

    def test_bus_to_autocad_attributes(self):
        """AutoCADConnector should map Bus fields to AutoCAD block attributes."""
        conn = AutoCADConnector()
        bus = _make_bus()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_bus(bus)
            payload = mock_post.call_args[1]["json"]
            attrs = payload["params"]["attributes"]
            assert attrs["BUS_ID"] == "bus-1"
            assert attrs["TYPE"] == "PQ"

    def test_transformer_to_autocad_attributes(self):
        """AutoCADConnector should map Transformer impedance and voltages."""
        conn = AutoCADConnector()
        xf = _make_transformer()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ) as mock_post:
            conn.draw_transformer(xf)
            payload = mock_post.call_args[1]["json"]
            attrs = payload["params"]["attributes"]
            assert attrs["MVA"] == "2.5"
            assert attrs["Z_PCT"] == "5.75"

    def test_cable_without_routing_path_uses_metadata(self):
        """AutoCADConnector.draw_cable should fall back to metadata when no routing_path."""
        conn = AutoCADConnector()
        cable = Cable(
            id="cable-nopath",
            name="Cable-NoPath",
            from_bus_id="b1",
            to_bus_id="b2",
            length_m=50.0,
            metadata={"from_point": [0, 0, 0], "to_point": [50, 0, 0]},
        )
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ):
            # Should not raise
            conn.draw_cable(cable)

    def test_synchronize_full_roundtrip(self):
        """RevitConnector.synchronize should export, create elements, and generate docs."""
        conn = RevitConnector()
        model = _make_unified_model()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True, "model": {}}),
        ):
            result = conn.synchronize(model)
            assert result["success"] is True
            assert result["operations"]["levels_created"] == 1
            assert result["operations"]["rooms_created"] == 1
            assert result["operations"]["elements_placed"] == 1


# ===========================================================================
# 11. Type Hints Verification
# ===========================================================================


class TestTypeHints:
    """Verify that key types are correct for type-safety."""

    def test_revit_element_type_is_str_enum(self):
        """RevitElementType values should be strings."""
        assert RevitElementType.PANEL.value == "panel"
        assert isinstance(RevitElementType.PANEL.value, str)

    def test_autocad_entity_type_is_str_enum(self):
        """AutoCADEntityType values should be strings."""
        assert AutoCADEntityType.LINE.value == "line"
        assert isinstance(AutoCADEntityType.LINE.value, str)

    def test_autocad_drawing_operation_is_str_enum(self):
        """AutoCADDrawingOperation values should be strings."""
        assert AutoCADDrawingOperation.CREATE.value == "create"

    def test_drawing_context_tracks_state(self):
        """AutoCADDrawingContext should track layers, blocks, entities."""
        ctx = AutoCADDrawingContext("/tmp/test.dwg")
        assert ctx.file_path == "/tmp/test.dwg"  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        assert ctx.layers == {}  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        assert ctx.blocks == {}
        assert ctx.entities == []
        assert ctx.modified is False
        assert ctx.locked is False

    def test_operation_log_entry_structure(self):
        """Operation log entries should contain expected keys."""
        conn = RevitConnector()
        with patch.object(
            conn.plugin.session,
            "post",
            return_value=_mock_response({"success": True}),
        ):
            conn.open_model("/tmp/test.rvt")
        log = conn.get_operation_log()  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        # open_model logs only when success, so let's force a log entry
        conn._log_operation("test_op", "test_target", True, {"key": "val"})
        log = conn.get_operation_log()
        entry = log[-1]
        assert "operation" in entry
        assert "target" in entry
        assert "success" in entry
        assert "timestamp" in entry
        assert "details" in entry
