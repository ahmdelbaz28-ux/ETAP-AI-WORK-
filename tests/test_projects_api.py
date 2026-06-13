"""
test_projects_api.py — Comprehensive tests for the Projects CRUD API endpoints.

Covers:
1. POST   /api/v1/projects               — Create project
2. GET    /api/v1/projects               — List projects
3. GET    /api/v1/projects/{id}          — Get single project
4. PUT    /api/v1/projects/{id}          — Update project
5. DELETE /api/v1/projects/{id}          — Soft-delete project
6. POST   /api/v1/projects/{id}/studies  — Run study on project
7. GET    /api/v1/projects/{id}/studies  — List study results

Run:
    pytest tests/test_projects_api.py -v
"""

from __future__ import annotations

import os
import sys
import uuid

import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# Helper
# ===========================================================================

def _create_project(client, auth_headers, name="Test Project", **overrides):
    """Create a project and return the response JSON."""
    payload = {"name": name, **overrides}
    resp = client.post(
        "/api/v1/projects/",
        headers=auth_headers,
        json=payload,
    )
    return resp


# ===========================================================================
# 1. POST /api/v1/projects — Create project
# ===========================================================================

class TestCreateProject:
    """Tests for project creation."""

    def test_create_project_success(self, client, auth_headers):
        """Creating a project with valid data returns 201."""
        resp = _create_project(client, auth_headers, name="My Power Project")
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["name"] == "My Power Project"
        assert data["status"] == "active"
        assert "id" in data
        assert data["created_by"] is not None

    def test_create_project_with_description(self, client, auth_headers):
        """Creating a project with a description succeeds."""
        resp = _create_project(
            client,
            auth_headers,
            name="Described Project",
            description="A test project with description",
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "A test project with description"

    def test_create_project_with_system_config(self, client, auth_headers):
        """Creating a project with a system_config dict succeeds."""
        config = {"base_mva": 100, "buses": [{"bus_id": 1}]}
        resp = _create_project(
            client,
            auth_headers,
            name="Configured Project",
            system_config=config,
        )
        assert resp.status_code == 201
        assert resp.json()["system_config"]["base_mva"] == 100

    def test_create_project_missing_name(self, client, auth_headers):
        """Creating a project without a name returns 422."""
        resp = client.post(
            "/api/v1/projects/",
            headers=auth_headers,
            json={"description": "No name project"},
        )
        assert resp.status_code == 422, f"Expected 422 for missing name, got {resp.status_code}"

    def test_create_project_no_auth(self, client):
        """Creating a project without auth returns 401."""
        resp = client.post(
            "/api/v1/projects/",
            json={"name": "Unauthorized"},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ===========================================================================
# 2. GET /api/v1/projects — List projects
# ===========================================================================

class TestListProjects:
    """Tests for listing projects."""

    def test_list_projects_success(self, client, auth_headers):
        """Listing projects returns 200 with a paginated response."""
        _create_project(client, auth_headers, name="Project A")
        _create_project(client, auth_headers, name="Project B")

        resp = client.get("/api/v1/projects/", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "projects" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] >= 2

    def test_list_projects_filter_by_status(self, client, auth_headers):
        """Listing projects with status filter works."""
        _create_project(client, auth_headers, name="Active Project")

        resp = client.get(
            "/api/v1/projects/?status_filter=active",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for p in data["projects"]:
            assert p["status"] == "active", "Only active projects should be returned"

    def test_list_projects_pagination(self, client, auth_headers):
        """Pagination parameters are respected."""
        # Create several projects
        for i in range(5):
            _create_project(client, auth_headers, name=f"Page Project {i}")

        resp = client.get(
            "/api/v1/projects/?page=1&page_size=2",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["projects"]) <= 2, "page_size should limit results"
        assert data["page"] == 1
        assert data["page_size"] == 2

    def test_list_projects_excludes_deleted(self, client, auth_headers):
        """Soft-deleted projects are excluded from default listing."""
        create_resp = _create_project(client, auth_headers, name="To Delete")
        project_id = create_resp.json()["id"]

        # Delete it
        client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)

        # List projects — should not include the deleted one
        resp = client.get("/api/v1/projects/", headers=auth_headers)
        assert resp.status_code == 200
        project_names = [p["name"] for p in resp.json()["projects"]]
        assert "To Delete" not in project_names


# ===========================================================================
# 3. GET /api/v1/projects/{id} — Get single project
# ===========================================================================

class TestGetProject:
    """Tests for retrieving a single project."""

    def test_get_existing_project(self, client, auth_headers):
        """Getting an existing project returns 200."""
        create_resp = _create_project(client, auth_headers, name="Fetchable Project")
        project_id = create_resp.json()["id"]

        resp = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["name"] == "Fetchable Project"
        assert resp.json()["id"] == project_id

    def test_get_nonexistent_project(self, client, auth_headers):
        """Getting a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/projects/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        assert "not found" in resp.json()["detail"].lower()

    def test_get_deleted_project(self, client, auth_headers):
        """Getting a soft-deleted project returns 410."""
        create_resp = _create_project(client, auth_headers, name="Deleted Project")
        project_id = create_resp.json()["id"]

        client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)

        resp = client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 410, f"Expected 410 for deleted project, got {resp.status_code}"


# ===========================================================================
# 4. PUT /api/v1/projects/{id} — Update project
# ===========================================================================

class TestUpdateProject:
    """Tests for updating a project."""

    def test_update_project_name(self, client, auth_headers):
        """Updating a project name succeeds."""
        create_resp = _create_project(client, auth_headers, name="Old Name")
        project_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
            json={"name": "New Name"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["name"] == "New Name"

    def test_update_project_description(self, client, auth_headers):
        """Updating the description succeeds."""
        create_resp = _create_project(client, auth_headers, name="Desc Update")
        project_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
            json={"description": "Updated description"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    def test_update_project_config(self, client, auth_headers):
        """Updating the system_config succeeds."""
        create_resp = _create_project(
            client, auth_headers, name="Config Update",
            system_config={"base_mva": 100},
        )
        project_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
            json={"system_config": {"base_mva": 200, "buses": []}},
        )
        assert resp.status_code == 200
        assert resp.json()["system_config"]["base_mva"] == 200

    def test_update_nonexistent_project(self, client, auth_headers):
        """Updating a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.put(
            f"/api/v1/projects/{fake_id}",
            headers=auth_headers,
            json={"name": "Ghost"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_update_cannot_set_deleted_status(self, client, auth_headers):
        """Setting status to 'deleted' via PUT is rejected."""
        create_resp = _create_project(client, auth_headers, name="Status Test")
        project_id = create_resp.json()["id"]

        resp = client.put(
            f"/api/v1/projects/{project_id}",
            headers=auth_headers,
            json={"status": "deleted"},
        )
        assert resp.status_code == 422, (
            f"Expected 422 for setting deleted via PUT, got {resp.status_code}"
        )


# ===========================================================================
# 5. DELETE /api/v1/projects/{id} — Soft-delete project
# ===========================================================================

class TestDeleteProject:
    """Tests for soft-deleting a project."""

    def test_soft_delete_success(self, client, auth_headers):
        """Deleting an active project returns 200."""
        create_resp = _create_project(client, auth_headers, name="Delete Me")
        project_id = create_resp.json()["id"]

        resp = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert "soft-deleted" in resp.json()["message"].lower()

    def test_delete_already_deleted(self, client, auth_headers):
        """Deleting an already-deleted project returns 410."""
        create_resp = _create_project(client, auth_headers, name="Already Gone")
        project_id = create_resp.json()["id"]

        # First delete
        client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)

        # Second delete attempt
        resp = client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 410, (
            f"Expected 410 for already-deleted project, got {resp.status_code}"
        )

    def test_delete_nonexistent_project(self, client, auth_headers):
        """Deleting a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.delete(f"/api/v1/projects/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"


# ===========================================================================
# 6. POST /api/v1/projects/{id}/studies — Run study
# ===========================================================================

class TestRunStudy:
    """Tests for running a study on a project."""

    def _create_project_with_config(self, client, auth_headers):
        """Helper: create a project with a basic system config."""
        config = {
            "base_mva": 100.0,
            "buses": [
                {"bus_id": 1, "voltage_magnitude": 1.05, "bus_type": "slack"},
                {"bus_id": 2, "voltage_magnitude": 1.0, "bus_type": "pq"},
            ],
            "lines": [
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2},
            ],
            "generators": [
                {"generator_id": 1, "bus_id": 1},
            ],
        }
        resp = _create_project(
            client,
            auth_headers,
            name="Study Project",
            system_config=config,
        )
        return resp.json()["id"]

    def test_run_study_load_flow(self, client, auth_headers):
        """Running a load-flow study returns 201."""
        project_id = self._create_project_with_config(client, auth_headers)

        resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "load_flow"},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["study_type"] == "load_flow"
        assert data["status"] in ("completed", "failed", "pending", "running"), (
            f"Unexpected study status: {data['status']}"
        )

    def test_run_study_invalid_type(self, client, auth_headers):
        """Running a study with an invalid type returns 422."""
        project_id = self._create_project_with_config(client, auth_headers)

        resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "invalid_study_type"},
        )
        assert resp.status_code == 422, f"Expected 422 for invalid study type, got {resp.status_code}"

    def test_run_study_nonexistent_project(self, client, auth_headers):
        """Running a study on a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/v1/projects/{fake_id}/studies",
            headers=auth_headers,
            json={"study_type": "load_flow"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_run_study_short_circuit(self, client, auth_headers):
        """Running a short-circuit study returns 201."""
        project_id = self._create_project_with_config(client, auth_headers)

        resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={
                "study_type": "short_circuit",
                "config": {"fault_type": "three_phase", "bus_id": 1},
            },
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"

    def test_run_study_on_deleted_project(self, client, auth_headers):
        """Running a study on a deleted project returns 410."""
        project_id = self._create_project_with_config(client, auth_headers)
        client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)

        resp = client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "load_flow"},
        )
        assert resp.status_code == 410, f"Expected 410, got {resp.status_code}"


# ===========================================================================
# 7. GET /api/v1/projects/{id}/studies — List study results
# ===========================================================================

class TestListStudies:
    """Tests for listing study results for a project."""

    def test_list_studies_success(self, client, auth_headers):
        """Listing studies for a project returns 200."""
        config = {"base_mva": 100.0}
        project_id = _create_project(
            client, auth_headers, name="Study List", system_config=config,
        ).json()["id"]

        # Run a study first
        client.post(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
            json={"study_type": "load_flow"},
        )

        resp = client.get(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "studies" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_studies_nonexistent_project(self, client, auth_headers):
        """Listing studies for a non-existent project returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.get(
            f"/api/v1/projects/{fake_id}/studies",
            headers=auth_headers,
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"

    def test_list_studies_empty(self, client, auth_headers):
        """Listing studies for a project with no studies returns an empty list."""
        project_id = _create_project(
            client, auth_headers, name="No Studies",
        ).json()["id"]

        resp = client.get(
            f"/api/v1/projects/{project_id}/studies",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["studies"] == []
