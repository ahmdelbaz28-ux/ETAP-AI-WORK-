"""Verification tests for F-5: complete acceleration_factor removal from solver parameters.

1. GET defaults must not contain acceleration_factor.
2. PUT with acceleration_factor must return HTTP 422 (fail-closed).
3. Complete round-trip (POST then GET) operates cleanly without the field.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_get_defaults_does_not_contain_acceleration_factor(client: TestClient):
    """GET /api/v1/studies/parameters must not include acceleration_factor in response."""
    resp = client.get("/api/v1/studies/parameters/")
    assert resp.status_code == 200
    data = resp.json()
    assert "convergence_tolerance" in data
    assert "max_iterations" in data
    assert "acceleration_factor" not in data


def test_put_with_acceleration_factor_returns_422(client: TestClient):
    """PUT /api/v1/studies/parameters containing acceleration_factor must fail with 422."""
    resp = client.put(
        "/api/v1/studies/parameters/",
        json={
            "convergence_tolerance": 1e-4,
            "max_iterations": 80,
            "acceleration_factor": 1.4,
        },
    )
    assert resp.status_code == 422


def test_post_and_get_roundtrip_without_acceleration_factor(client: TestClient):
    """POST /api/v1/studies/parameters creates parameters and GET retrieves them cleanly."""
    post_resp = client.post(
        "/api/v1/studies/parameters/",
        json={
            "convergence_tolerance": 2e-5,
            "max_iterations": 95,
        },
    )
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["convergence_tolerance"] == 2e-5
    assert post_data["max_iterations"] == 95
    assert "acceleration_factor" not in post_data

    get_resp = client.get("/api/v1/studies/parameters/")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["convergence_tolerance"] == 2e-5
    assert get_data["max_iterations"] == 95
    assert "acceleration_factor" not in get_data
