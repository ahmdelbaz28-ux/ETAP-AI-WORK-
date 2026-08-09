"""
Unit tests for NVIDIA CAD to SimReady API Router (/api/v1/cad-simready)
"""

import os
import pytest
from fastapi.testclient import TestClient

from api.routes import app

client = TestClient(app)


def test_get_simready_status():
    """Test /api/v1/cad-simready/status endpoint."""
    response = client.get("/api/v1/cad-simready/status")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "engine" in data["data"]
    assert data["data"]["status"] == "ready"


def test_get_material_presets():
    """Test /api/v1/cad-simready/presets endpoint."""
    response = client.get("/api/v1/cad-simready/presets")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["presets"], list)
    assert len(data["presets"]) > 0
    assert data["presets"][0]["id"] == "industrial_copper_steel"


def test_convert_cad_to_simready():
    """Test /api/v1/cad-simready/convert endpoint."""
    payload = {
        "source_filename": "substation_layout.dxf",
        "asset_name": "Main_Substation_138kV",
        "enable_physics": True,
        "material_preset": "industrial_copper_steel",
        "lod_level": "high",
        "export_usdz": True,
    }
    response = client.post("/api/v1/cad-simready/convert", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["asset_name"] == "Main_Substation_138kV"
    assert data["output_usd_path"].endswith(".usda")
    assert data["output_usdz_path"].endswith(".usdz")
    assert data["physics_bound"] is True
    assert len(data["nodes"]) > 0
