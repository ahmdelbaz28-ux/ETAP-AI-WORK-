"""
Unit tests for NVIDIA CAD to SimReady API Router (/api/v1/cad-simready)
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_api_key
from api.routes import app

HEADERS = {"X-API-Key": "test-key"}


@pytest.fixture
def simready_client():
    app.dependency_overrides[get_api_key] = lambda: "test-key"
    client = TestClient(app, raise_server_exceptions=False)
    try:
        yield client
    finally:
        client.close()
        app.dependency_overrides.pop(get_api_key, None)


def test_get_simready_status(simready_client):
    """Test /api/v1/cad-simready/status endpoint."""
    response = simready_client.get("/api/v1/cad-simready/status", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "engine" in data["data"]
    assert data["data"]["status"] == "ready"


def test_get_material_presets(simready_client):
    """Test /api/v1/cad-simready/presets endpoint."""
    response = simready_client.get("/api/v1/cad-simready/presets", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["presets"], list)
    assert len(data["presets"]) > 0
    assert data["presets"][0]["id"] == "industrial_copper_steel"


def test_convert_cad_to_simready(simready_client):
    """Test /api/v1/cad-simready/convert endpoint."""
    payload = {
        "source_filename": "substation_layout.dxf",
        "asset_name": "Main_Substation_138kV",
        "enable_physics": True,
        "material_preset": "industrial_copper_steel",
        "lod_level": "high",
        "export_usdz": True,
    }
    response = simready_client.post("/api/v1/cad-simready/convert", json=payload, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["asset_name"] == "Main_Substation_138kV"
    assert data["output_usd_path"].endswith(".usda")
    assert data["output_usdz_path"].endswith(".usdz")
    assert data["physics_bound"] is True
    assert len(data["nodes"]) > 0
