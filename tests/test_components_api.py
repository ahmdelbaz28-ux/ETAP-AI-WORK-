"""
tests/test_components_api.py — Unit and integration tests for Component Library API.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.dependencies import CurrentUser, get_current_user_from_header
from api.routes import app


@pytest.fixture
def engineer_user():
    return CurrentUser(
        user_id="eng-123",
        username="engineer_bob",
        email="bob@etap.com",
        role="engineer",
        tenant_id="tenant-alpha",
    )


@pytest.fixture
def admin_user():
    return CurrentUser(
        user_id="admin-999",
        username="admin_alice",
        email="alice@etap.com",
        role="admin",
        tenant_id="tenant-alpha",
    )


@pytest.fixture
def viewer_user():
    return CurrentUser(
        user_id="view-456",
        username="viewer_carol",
        email="carol@etap.com",
        role="viewer",
        tenant_id="tenant-alpha",
    )


def test_seed_components_and_list(client: TestClient) -> None:
    """Test that seed components are automatically loaded and returned."""
    res = client.get("/api/v1/components")
    assert res.status_code == 200
    data = res.json()
    assert "components" in data
    assert "total" in data
    assert data["total"] >= 20  # 10 cables + 5 transformers + 5 breakers + 3 templates
    assert len(data["components"]) > 0

    # Ensure all returned items have required fields
    first = data["components"][0]
    assert "id" in first
    assert "name" in first
    assert "type" in first
    assert "category" in first
    assert first["is_verified"] is True


def test_filter_components(client: TestClient) -> None:
    """Test filtering by type, standard, and search query."""
    # Filter by type=cable
    res_cables = client.get("/api/v1/components?type=cable")
    assert res_cables.status_code == 200
    cables_data = res_cables.json()
    assert cables_data["total"] >= 10
    for comp in cables_data["components"]:
        assert comp["type"] == "cable"

    # Filter by standard
    res_std = client.get("/api/v1/components?standard=IEC 60364")
    assert res_std.status_code == 200
    std_data = res_std.json()
    assert std_data["total"] >= 10
    for comp in std_data["components"]:
        assert any("IEC 60364" in s for s in comp["standards"])

    # Search query
    res_search = client.get("/api/v1/components?search=PVC")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["total"] >= 1


def test_types_and_standards_counts(client: TestClient) -> None:
    """Test aggregation endpoints for types and standards."""
    res_types = client.get("/api/v1/components/types")
    assert res_types.status_code == 200
    types = res_types.json()
    assert isinstance(types, list)
    type_names = [t["type"] for t in types]
    assert "cable" in type_names
    assert "transformer" in type_names
    assert "breaker" in type_names

    res_stds = client.get("/api/v1/components/standards")
    assert res_stds.status_code == 200
    stds = res_stds.json()
    assert isinstance(stds, list)
    std_names = [s["standard"] for s in stds]
    assert any("IEC" in s or "IEEE" in s for s in std_names)


def test_get_component_by_id(client: TestClient) -> None:
    """Test retrieving a single component by its ID."""
    res_list = client.get("/api/v1/components?type=cable&page_size=1")
    assert res_list.status_code == 200
    items = res_list.json()["components"]
    assert len(items) > 0
    cid = items[0]["id"]

    res_single = client.get(f"/api/v1/components/{cid}")
    assert res_single.status_code == 200
    comp = res_single.json()
    assert comp["id"] == cid
    assert comp["name"] == items[0]["name"]

    res_404 = client.get("/api/v1/components/non-existent-id-0000")
    assert res_404.status_code == 404


def test_contribute_and_admin_review_workflow(
    client: TestClient,
    engineer_user: CurrentUser,
    admin_user: CurrentUser,
) -> None:
    """Test end-to-end community contribution, pending queue, and admin verification."""
    # 1. Engineer submits a community component
    app.dependency_overrides[get_current_user_from_header] = lambda: engineer_user

    submission = {
        "type": "cable",
        "category": "LV Power",
        "subcategory": "Copper XLPE",
        "name": "Custom Community Cable 4x185mm²",
        "manufacturer": "Prysmian",
        "model_number": "PRY-XLPE-185",
        "specs": {
            "cross_section_mm2": 185.0,
            "conductor_material": "Cu",
            "insulation": "XLPE",
            "rated_voltage_kv": 1.0,
            "ampacity_ground_a": 410.0,
            "r_per_km_ohm": 0.0991,
            "x_per_km_ohm": 0.075,
        },
        "standards": ["IEC 60502-1"],
        "tags": ["lv", "community", "xlpe"],
        "contributor_notes": "Tested in industrial substation feed",
    }

    res_post = client.post("/api/v1/components/contribute", json=submission)
    assert res_post.status_code == 201
    created = res_post.json()
    comp_id = created["id"]
    assert created["is_verified"] is False
    assert created["review_status"] == "pending"
    assert created["name"] == submission["name"]

    # 2. Check pending queue as admin
    app.dependency_overrides[get_current_user_from_header] = lambda: admin_user
    res_pending = client.get("/api/v1/components/pending")
    assert res_pending.status_code == 200
    pending_items = res_pending.json()
    pending_ids = [p["id"] for p in pending_items]
    assert comp_id in pending_ids

    # 3. Admin verifies and approves the component
    res_verify = client.post(
        f"/api/v1/components/{comp_id}/verify",
        json={"notes": "Parameters verified against manufacturer catalog."},
    )
    assert res_verify.status_code == 200
    verified_data = res_verify.json()
    assert verified_data["is_verified"] is True
    assert verified_data["review_status"] == "approved"
    assert verified_data["reviewed_by"] == admin_user.user_id

    # 4. Confirm it now appears in public verified catalog
    app.dependency_overrides.clear()
    res_public = client.get(f"/api/v1/components/{comp_id}")
    assert res_public.status_code == 200
    assert res_public.json()["is_verified"] is True


def test_contribute_and_reject_workflow(
    client: TestClient,
    engineer_user: CurrentUser,
    admin_user: CurrentUser,
) -> None:
    """Test admin rejection flow with rejection reason."""
    app.dependency_overrides[get_current_user_from_header] = lambda: engineer_user

    submission = {
        "type": "breaker",
        "category": "MV Vacuum",
        "name": "Dubious Breaker with Missing Data",
        "specs": {"voltage_kv": 12.0},
        "standards": [],
        "tags": ["incomplete"],
    }

    res_post = client.post("/api/v1/components/contribute", json=submission)
    assert res_post.status_code == 201
    comp_id = res_post.json()["id"]

    # Admin rejects
    app.dependency_overrides[get_current_user_from_header] = lambda: admin_user
    res_reject = client.post(
        f"/api/v1/components/{comp_id}/reject",
        json={"reason": "Missing interrupting rating (Icu) and test certificate reference."},
    )
    assert res_reject.status_code == 200
    rejected = res_reject.json()
    assert rejected["review_status"] == "rejected"
    assert "Missing interrupting rating" in rejected["review_notes"]


def test_etap_xml_bulk_import(
    client: TestClient,
    engineer_user: CurrentUser,
) -> None:
    """Test importing components from an ETAP project XML file."""
    app.dependency_overrides[get_current_user_from_header] = lambda: engineer_user

    sample_etap_xml = """<?xml version="1.0" encoding="utf-8"?>
<EtapProject Version="21.0">
  <System>
    <Cable ID="CBL_FEEDER_01" Type="Cu" Size="240" Voltage="11" Insulation="XLPE" Length="350" Unit="m" R="0.098" X="0.082" Ampacity="450" Standard="IEC 60502" />
    <Transformer ID="TX_MAIN_01" PrimKV="11" SecKV="0.4" MVA="2.5" ImpedanceZ="6.0" XRRatio="8.5" Type="Cast Resin" Standard="IEC 60076" />
    <Breaker ID="CB_INCOMER_01" RatedKV="12" ContinuousAmps="1250" InterruptingKA="25" Standard="IEC 62271-100" />
  </System>
</EtapProject>
"""
    files = {
        "file": ("test_project.xml", sample_etap_xml.encode("utf-8"), "application/xml"),
    }
    res = client.post("/api/v1/components/import/etap", files=files)
    assert res.status_code == 200
    imported = res.json()
    assert len(imported) == 3
    names = [c["name"] for c in imported]
    assert "CBL_FEEDER_01" in names
    assert "TX_MAIN_01" in names
    assert "CB_INCOMER_01" in names

    # Confirm imported items are marked source="etap-import" and verified
    for c in imported:
        assert c["source"] == "etap-import"
        assert c["is_verified"] is True


def test_anonymous_requests_rejected_when_auth_enabled(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anonymous requests (client.get('/api/v1/components')) must return 401 or 403 when auth is active."""
    monkeypatch.setenv("ENGINEERING_SERVICE_AUTH_DISABLED", "false")
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "real-prod-api-key-32-chars-long!")

    res = client.get("/api/v1/components")
    assert res.status_code in (401, 403)

    res_types = client.get("/api/v1/components/types")
    assert res_types.status_code in (401, 403)

    res_stds = client.get("/api/v1/components/standards")
    assert res_stds.status_code in (401, 403)

    res_single = client.get("/api/v1/components/cable-sample-id")
    assert res_single.status_code in (401, 403)

    # Valid API Key should succeed
    headers = {"X-API-Key": "real-prod-api-key-32-chars-long!"}
    res_auth = client.get("/api/v1/components", headers=headers)
    assert res_auth.status_code == 200


def test_json_import_ignores_user_supplied_ids(
    client: TestClient,
    admin_user: CurrentUser,
) -> None:
    """JSON import endpoint must never accept user-provided IDs (IDOR protection)."""
    app.dependency_overrides[get_current_user_from_header] = lambda: admin_user

    attacker_chosen_id = "injected-custom-id-9999"
    payload = [
        {
            "id": attacker_chosen_id,
            "type": "cable",
            "category": "LV Power",
            "name": "Security Test Injected ID Cable",
            "specs": {"voltage_kv": 1.0},
        }
    ]

    files = {
        "file": (
            "components.json",
            json.dumps(payload).encode("utf-8"),
            "application/json",
        ),
    }
    res = client.post("/api/v1/components/import/json", files=files)
    assert res.status_code == 200
    imported = res.json()
    assert len(imported) == 1
    # Verify the generated ID is NOT what the user provided
    assert imported[0]["id"] != attacker_chosen_id
    assert imported[0]["name"] == "Security Test Injected ID Cable"


def test_pending_queue_tenant_isolation(
    client: TestClient,
    admin_user: CurrentUser,
) -> None:
    """Test tenant filtering on pending submissions for non-platform admin."""
    app.dependency_overrides[get_current_user_from_header] = lambda: admin_user
    res = client.get("/api/v1/components/pending")
    assert res.status_code == 200


def test_category_regex_validation(
    client: TestClient,
    engineer_user: CurrentUser,
) -> None:
    """Test regex pattern enforcement on category and subcategory."""
    app.dependency_overrides[get_current_user_from_header] = lambda: engineer_user

    invalid_submission = {
        "type": "cable",
        "category": "LV Power $#@!",  # Invalid special chars not matching ^[a-zA-Z0-9\s\-_/]+$
        "name": "Invalid Regex Cable",
        "specs": {"voltage_kv": 1.0},
    }
    res = client.post("/api/v1/components/contribute", json=invalid_submission)
    assert res.status_code == 422  # Unprocessable Entity from pydantic regex
