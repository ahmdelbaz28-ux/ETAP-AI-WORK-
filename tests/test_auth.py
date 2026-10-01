"""
tests/test_auth.py — Regression tests for Authentication & Authorization security fixes.
"""

from __future__ import annotations

import pytest

TEST_USER_PASSWORD = "S3cureP@ss!"


def test_deactivated_user_jwt_bypass_rejected(client, admin_headers):
    """Fix 9: Deactivated user access token must return 401."""
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "deact_user_reg",
            "email": "deact_user_reg@example.com",
            "password": TEST_USER_PASSWORD,
        },
    )
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": "deact_user_reg",
            "password": TEST_USER_PASSWORD,
        },
    )
    assert login_resp.status_code == 200
    access_token = login_resp.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {access_token}"}

    me_before = client.get("/api/v1/auth/me", headers=user_headers)
    assert me_before.status_code == 200

    del_resp = client.delete(f"/api/v1/auth/users/{user_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    me_after = client.get("/api/v1/auth/me", headers=user_headers)
    assert me_after.status_code == 401
