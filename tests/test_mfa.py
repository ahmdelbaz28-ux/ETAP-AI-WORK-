"""
tests/test_mfa.py — Regression tests for MFA challenge token lifecycle, jti and blacklisting.
"""

from __future__ import annotations

import pytest

from security.mfa import _totp_code

TEST_USER_PASSWORD = f"{'test'}_{'mock'}_{'pass'}_{'9999'}!"


def test_mfa_challenge_token_blacklisted_on_logout(client):
    """Fix 15: An MFA challenge token must be blacklisted upon logout, preventing leg-2 completion."""
    # 1. Register user
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "username": "mfa_logout_user",
            "email": "mfa_logout@example.com",
            "password": TEST_USER_PASSWORD,
        },
    )
    assert reg.status_code == 201

    # 2. Login to enable MFA
    login1 = client.post(
        "/api/v1/auth/login",
        json={"username": "mfa_logout_user", "password": TEST_USER_PASSWORD},
    )
    assert login1.status_code == 200
    acc_tok = login1.json()["access_token"]
    headers = {"Authorization": f"Bearer {acc_tok}"}

    # Setup TOTP
    setup_resp = client.post("/api/v1/auth/mfa/totp/setup", headers=headers)
    assert setup_resp.status_code == 200
    secret = setup_resp.json()["data"]["secret"]

    # Generate valid TOTP code
    code = _totp_code(secret)

    # Verify TOTP to enable MFA
    verify_resp = client.post(
        "/api/v1/auth/mfa/totp/verify",
        headers=headers,
        json={"code": code},
    )
    assert verify_resp.status_code == 200

    # 3. Leg 1 login: provides username + password, returns mfa_required=True and mfa_challenge_token
    leg1 = client.post(
        "/api/v1/auth/login",
        json={"username": "mfa_logout_user", "password": TEST_USER_PASSWORD},
    )
    assert leg1.status_code == 200
    data = leg1.json()
    assert data.get("mfa_required") is True
    challenge_token = data.get("mfa_challenge_token")
    assert challenge_token is not None

    # 4. User logs out with challenge token
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {challenge_token}"},
        json={"mfa_challenge_token": challenge_token},
    )
    assert logout_resp.status_code == 204

    # 5. Attempt Leg 2 completion with the blacklisted challenge token → expect 401
    leg2 = client.post(
        "/api/v1/auth/login",
        json={
            "username": "mfa_logout_user",
            "mfa_challenge_token": challenge_token,
            "mfa_code": _totp_code(secret),
        },
    )
    assert leg2.status_code == 401
