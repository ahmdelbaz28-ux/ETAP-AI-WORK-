"""
tests/test_data_import.py — Tests for CIM/XML data import parsing and preview.

Verifies:
1. defusedxml is loaded without fallback to stdlib xml.etree.ElementTree.
2. Direct CIM/XML parsing with _parse_cim_xml extracts TopologicalNode and ACLineSegment.
3. POST /api/v1/import/preview processes CIM/XML files cleanly and returns structured preview.
"""

from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import api.data_import as data_import_mod
import api.feature_flags as feature_flags_mod
from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header

CIM_XML_CONTENT = b"""<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:cim="http://iec.ch/TC57/2013/CIM-schema-cim16#">
  <cim:TopologicalNode rdf:ID="_bus_01">
    <cim:IdentifiedObject.name>Bus 1 115kV</cim:IdentifiedObject.name>
  </cim:TopologicalNode>
  <cim:TopologicalNode rdf:ID="_bus_02">
    <cim:IdentifiedObject.name>Bus 2 115kV</cim:IdentifiedObject.name>
  </cim:TopologicalNode>
  <cim:ACLineSegment rdf:ID="_line_01">
    <cim:IdentifiedObject.name>Line 1-2</cim:IdentifiedObject.name>
  </cim:ACLineSegment>
</rdf:RDF>
"""

TEST_USER = CurrentUser(
    user_id="test_user_import",
    username="test_importer",
    email="importer@etap.local",
    role="engineer",
    tenant_id="tenant_cim_test",
)


@pytest.fixture
def import_client(monkeypatch):
    """FastAPI TestClient with data_import router and authentication overridden."""
    monkeypatch.setattr(feature_flags_mod, "is_feature_enabled", lambda *args, **kwargs: True)

    app = FastAPI()
    app.include_router(data_import_mod.router)
    app.dependency_overrides[get_current_user_from_header] = lambda: TEST_USER
    app.dependency_overrides[get_api_key] = lambda: "test-api-key"

    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


class TestCimXmlImport:
    """Test suite for CIM/XML import parsing and preview."""

    def test_defusedxml_is_active_not_stdlib(self):
        """Verify defusedxml is installed and used; stdlib xml fallback is forbidden."""
        assert data_import_mod.ET is not None, "defusedxml must be installed and active"
        assert getattr(data_import_mod.ET, "__name__", "") == "defusedxml.ElementTree", (
            f"Expected defusedxml.ElementTree, got {getattr(data_import_mod.ET, '__name__', '')}"
        )

    def test_cim_xml_direct_parsing(self):
        """Direct parsing of CIM/XML payload extracts buses, lines, and version."""
        buses, branches, metadata, warnings = data_import_mod._parse_cim_xml(CIM_XML_CONTENT)
        assert len(buses) == 2
        assert buses[0].id == "_bus_01"
        assert buses[0].name == "Bus 1 115kV"
        assert buses[1].id == "_bus_02"
        assert len(branches) == 1
        assert branches[0].id == "_line_01"
        assert metadata.get("cim_version") == "IEC 61970"
        assert len(warnings) > 0

    def test_cim_xml_preview_endpoint(self, import_client: TestClient):
        """POST /api/v1/import/preview with CIM/XML file returns 200 and parsed topology."""
        files = {
            "file": ("substation_model.xml", io.BytesIO(CIM_XML_CONTENT), "application/xml")
        }
        res = import_client.post("/api/v1/import/preview", files=files)
        assert res.status_code == 200, f"Preview failed: {res.text}"
        data = res.json()
        assert data["format"] == "cim-xml"
        assert data["filename"] == "substation_model.xml"
        assert data["buses_count"] == 2
        assert data["branches_count"] == 1
        assert data["records_count"] == 3
        assert "preview_id" in data
        assert data["risk_level"] in ("low", "medium", "high")
