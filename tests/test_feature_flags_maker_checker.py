"""tests/test_feature_flags_maker_checker.py — Verify Maker-Checker enforcement and concurrency locking on feature flags."""

from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import api.feature_flags as ff
from api.dependencies import CurrentUser, get_api_key, get_current_user_from_header


@pytest.fixture
def ff_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / "flags.json"
    db_file.write_text(json.dumps(ff.DEFAULT_FEATURE_FLAGS), encoding="utf-8")
    monkeypatch.setenv("FEATURE_FLAGS_PATH", str(db_file))
    monkeypatch.setenv("ENGINEERING_SERVICE_API_KEY", "secret-admin-key")

    app = FastAPI()
    app.include_router(ff.router)
    return app, db_file


def test_put_feature_flag_maker_checker_enforcement(ff_app):
    app, db_file = ff_app
    client = TestClient(app)

    # 1. Non-admin user (role="engineer") -> 403 MAKER_CHECKER_VIOLATION
    app.dependency_overrides[get_api_key] = lambda: "secret-admin-key"
    app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
        user_id="eng-1",
        username="engineer",
        email="eng@example.com",
        role="engineer",
    )

    res = client.put(
        "/api/v1/feature-flags/harmonic_analysis",
        json={"enabled": True},
        headers={"X-API-Key": "secret-admin-key", "Authorization": "Bearer fake-token"},
    )
    assert res.status_code == 403
    assert "MAKER_CHECKER_VIOLATION" in res.json()["detail"]

    # 2. Admin user (role="admin") -> 200 OK
    app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
        user_id="admin-1",
        username="admin",
        email="admin@example.com",
        role="admin",
    )

    res = client.put(
        "/api/v1/feature-flags/harmonic_analysis",
        json={"enabled": True},
        headers={"X-API-Key": "secret-admin-key", "Authorization": "Bearer fake-token"},
    )
    assert res.status_code == 200
    assert res.json()["enabled"] is True

    # 3. GET read remains accessible with API key alone
    res_get = client.get("/api/v1/feature-flags/harmonic_analysis", headers={"X-API-Key": "secret-admin-key"})
    assert res_get.status_code == 200
    assert res_get.json()["enabled"] is True


def test_concurrent_put_feature_flags(ff_app):
    """Verify thread-safety and atomic updates under concurrent load."""
    app, db_file = ff_app
    client = TestClient(app)

    app.dependency_overrides[get_api_key] = lambda: "secret-admin-key"
    app.dependency_overrides[get_current_user_from_header] = lambda: CurrentUser(
        user_id="admin-1",
        username="admin",
        email="admin@example.com",
        role="admin",
    )

    flags_to_toggle = ["harmonic_analysis", "motor_starting", "transient_stability", "optimal_power_flow"]

    def toggle_flag(flag_name: str, enable: bool):
        return client.put(
            f"/api/v1/feature-flags/{flag_name}",
            json={"enabled": enable},
            headers={"X-API-Key": "secret-admin-key", "Authorization": "Bearer admin-token"},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for i in range(20):
            flag = flags_to_toggle[i % len(flags_to_toggle)]
            enable = (i % 2 == 0)
            futures.append(executor.submit(toggle_flag, flag, enable))

        responses = [f.result() for f in futures]

    # Every concurrent PUT must return 200 with no race condition or corruption
    for r in responses:
        assert r.status_code == 200

    # Ensure JSON file remains valid and uncorrupted
    data = json.loads(db_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    for k in flags_to_toggle:
        assert k in data
