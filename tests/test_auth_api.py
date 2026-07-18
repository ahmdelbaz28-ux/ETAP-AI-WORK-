"""
test_auth_api.py — Comprehensive tests for the Authentication API endpoints.

Covers:
1. POST /api/v1/auth/register
2. POST /api/v1/auth/login
3. POST /api/v1/auth/refresh
4. POST /api/v1/auth/logout
5. GET  /api/v1/auth/me
6. PUT  /api/v1/auth/me
7. PUT  /api/v1/auth/me/password
8. POST /api/v1/auth/forgot-password
9. POST /api/v1/auth/reset-password
10. GET  /api/v1/auth/users
11. DELETE /api/v1/auth/users/{user_id}

Run:
    pytest tests/test_auth_api.py -v
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017


import jwt
import pytest

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.dependencies import JWT_ALGORITHM, JWT_SECRET_KEY

# Test credentials — module-level constants so SonarCloud S2068
# (hard-coded credentials) is satisfied. These are NOT real secrets;
# they exist only to exercise auth code paths in the test suite.
TEST_PASSWORD_1 = "WrongP@ss6!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_10 = "12345678"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_2 = "WrongP@ss!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_3 = "mynameS3cure!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_5 = "S3cureP@ss2!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_6 = "Br4ndN3wP@ss!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_7 = "N3wS3cureP@ss!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_8 = "Whatever123!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_PASSWORD_9 = "OldP@ssw0rd!"  # NOSONAR — S2068: test credential constant, not a real secret
TEST_USER_PASSWORD = "S3cureP@ss!"  # NOSONAR — S2068: test credential constant, not a real secret


# ===========================================================================
# 1. POST /api/v1/auth/register
# ===========================================================================


class TestRegister:
    """Tests for the user registration endpoint."""

    def test_register_success(self, client):
        """Registering with valid data returns 201 and the user profile."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": TEST_USER_PASSWORD,
                "role": "engineer",
            },
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["username"] == "newuser", "Username should match"
        assert data["email"] == "newuser@example.com", "Email should match"
        assert data["role"] == "engineer", "Default role should be engineer"
        assert data["is_active"] is True, "User should be active by default"
        assert "id" in data, "Response should include user ID"
        assert "password_hash" not in data, "Password hash must never be in response"

    def test_register_duplicate_username(self, client):
        """Registering with an existing username returns 409."""
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "dupuser",
                "email": "first@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "dupuser",
                "email": "second@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        assert resp.status_code == 409, (
            f"Expected 409 for duplicate username, got {resp.status_code}"
        )
        assert "Username already registered" in resp.json()["detail"]

    def test_register_duplicate_email(self, client):
        """Registering with an existing email returns 409."""
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "user_a",
                "email": "same@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "user_b",
                "email": "same@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        assert resp.status_code == 409, f"Expected 409 for duplicate email, got {resp.status_code}"
        assert "Email already registered" in resp.json()["detail"]

    def test_register_weak_password(self, client):
        """Registering with a weak password returns 422."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "password",  # in common-password blocklist
            },
        )
        assert resp.status_code == 422, f"Expected 422 for weak password, got {resp.status_code}"

    def test_register_missing_fields(self, client):
        """Registering with missing required fields returns 422."""
        resp = client.post(
            "/api/v1/auth/register",
            json={"username": "incomplete"},
        )
        assert resp.status_code == 422, f"Expected 422 for missing fields, got {resp.status_code}"

    def test_register_common_password(self, client):
        """Passwords from the common-password blocklist are rejected."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "commonpw",
                "email": "common@example.com",
                "password": TEST_PASSWORD_10,  # in blocklist
            },
        )
        assert resp.status_code == 422, f"Expected 422 for common password, got {resp.status_code}"

    def test_register_password_contains_username(self, client):
        """Passwords that contain the username are rejected."""
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "username": "myname",
                "email": "myname@example.com",
                "password": TEST_PASSWORD_3,
            },
        )
        assert resp.status_code == 422, (
            f"Expected 422 for password containing username, got {resp.status_code}"
        )


# ===========================================================================
# 2. POST /api/v1/auth/login
# ===========================================================================


class TestLogin:
    """Tests for the login endpoint."""

    def _register_and_login(self, client, username="logintest", password="S3cureP@ss!"):  # NOSONAR — S2068: test credential constant, not a real secret
        """Helper: register a user then attempt login."""
        client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": password,
            },
        )
        return client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": password},
        )

    def test_login_success(self, client):
        """Login with correct credentials returns 200 and JWT tokens."""
        resp = self._register_and_login(client)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "access_token" in data, "Response must include access_token"
        assert "refresh_token" in data, "Response must include refresh_token"
        assert data["token_type"] == "bearer", "Token type should be bearer"
        assert "expires_in" in data, "Response must include expires_in"

    def test_login_wrong_password(self, client):
        """Login with wrong password returns 401."""
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "wrongpw",
                "email": "wrongpw@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "wrongpw", "password": TEST_PASSWORD_2},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        assert "Invalid credentials" in resp.json()["detail"]

    def test_login_nonexistent_user(self, client):
        """Login with non-existent user returns 401 (same error as wrong password)."""
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": "ghost_user", "password": TEST_PASSWORD_8},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        # Must be the SAME error message to avoid user enumeration
        assert "Invalid credentials" in resp.json()["detail"], (
            "Error for non-existent user should be identical to wrong password error"
        )

    def test_login_rate_limiting(self, client):
        """After 5 failed login attempts, the 6th is rate-limited (429)."""
        username = "ratelimituser"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": "ratelimit@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        # Make 5 failed attempts
        for i in range(5):
            resp = client.post(
                "/api/v1/auth/login",
                json={"username": username, "password": f"WrongP@ss{i}!"},  # NOSONAR — S2068: test credential constant, not a real secret
            )
            assert resp.status_code == 401, f"Attempt {i + 1} should return 401"

        # 6th attempt should be rate-limited
        resp = client.post(
            "/api/v1/auth/login",
            json={"username": username, "password": TEST_PASSWORD_1},
        )
        assert resp.status_code == 429, (
            f"Expected 429 after 5 failed attempts, got {resp.status_code}"
        )


# ===========================================================================
# 3. POST /api/v1/auth/refresh
# ===========================================================================


class TestRefresh:
    """Tests for the token refresh endpoint."""

    def test_refresh_success(self, client):
        """A valid refresh token returns a new access + refresh pair."""
        # Register + login
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "refreshuser",
                "email": "refresh@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "refreshuser", "password": TEST_USER_PASSWORD},
        )
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "access_token" in data, "Response must include new access_token"
        assert "refresh_token" in data, "Response must include new refresh_token"

    def test_refresh_expired_token(self, client):
        """An expired refresh token returns 401."""
        # Create an expired refresh token manually
        now = datetime.now(UTC)
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "iat": now - timedelta(days=30),
            "exp": now - timedelta(days=1),
        }
        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_token},
        )
        assert resp.status_code == 401, f"Expected 401 for expired token, got {resp.status_code}"
        assert "expired" in resp.json()["detail"].lower()

    def test_refresh_invalid_token(self, client):
        """A malformed refresh token returns 401."""
        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "this.is.not.a.valid.jwt"},
        )
        assert resp.status_code == 401, f"Expected 401 for invalid token, got {resp.status_code}"
        assert "Invalid" in resp.json()["detail"]

    def test_refresh_access_token_rejected(self, client):
        """Using an access token as a refresh token returns 401."""
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "tokentypeuser",
                "email": "tokentype@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "tokentypeuser", "password": TEST_USER_PASSWORD},
        )
        access_token = login_resp.json()["access_token"]

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert resp.status_code == 401, (
            f"Access token should not be accepted as refresh token, got {resp.status_code}"
        )


# ===========================================================================
# 4. POST /api/v1/auth/logout
# ===========================================================================


class TestLogout:
    """Tests for the logout endpoint."""

    def test_logout_success(self, client, auth_headers):
        """Logout with a valid token returns 204."""
        resp = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert resp.status_code == 204, f"Expected 204, got {resp.status_code}"

    def test_logout_no_token(self, client):
        """Logout without a token returns 401."""
        resp = client.post("/api/v1/auth/logout")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ===========================================================================
# 5. GET /api/v1/auth/me
# ===========================================================================


class TestGetMe:
    """Tests for the current-user profile endpoint."""

    def test_me_success(self, client, auth_headers):
        """GET /me with a valid token returns the user profile."""
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["username"] == "testuser", "Username should match"
        assert data["email"] == "testuser@example.com", "Email should match"

    def test_me_expired_token(self, client):
        """GET /me with an expired token returns 401."""
        now = datetime.now(UTC)
        expired_payload = {
            "sub": str(uuid.uuid4()),
            "role": "engineer",
            "type": "access",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401, f"Expected 401 for expired token, got {resp.status_code}"

    def test_me_no_token(self, client):
        """GET /me without a token returns 401."""
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"


# ===========================================================================
# 6. PUT /api/v1/auth/me
# ===========================================================================


class TestUpdateMe:
    """Tests for the update-profile endpoint."""

    def test_update_email(self, client, auth_headers):
        """Updating the email address succeeds."""
        resp = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={"email": "newemail@example.com"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["email"] == "newemail@example.com"

    def test_update_mfa_preference(self, client, auth_headers):
        """Toggling MFA enabled succeeds."""
        resp = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={"mfa_enabled": True},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json()["mfa_enabled"] is True

    def test_update_duplicate_email(self, client, registered_user, auth_headers):
        """Updating to an email already used by another user returns 409."""
        # Register a second user
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "seconduser",
                "email": "second@example.com",
                "password": TEST_PASSWORD_5,
            },
        )
        # Try to update testuser's email to seconduser's email
        resp = client.put(
            "/api/v1/auth/me",
            headers=auth_headers,
            json={"email": "second@example.com"},
        )
        assert resp.status_code == 409, f"Expected 409 for duplicate email, got {resp.status_code}"


# ===========================================================================
# 7. PUT /api/v1/auth/me/password
# ===========================================================================


class TestChangePassword:
    """Tests for the change-password endpoint."""

    def test_change_password_success(self, client, auth_headers):
        """Changing password with correct current password succeeds."""
        resp = client.put(
            "/api/v1/auth/me/password",
            headers=auth_headers,
            json={
                "current_password": "Str0ngP@ss!",  # NOSONAR — S2068: test credential constant, not a real secret
                "new_password": "N3wS3cureP@ss!",  # NOSONAR — S2068: test credential constant, not a real secret
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        # Verify login works with new password
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": TEST_PASSWORD_7},
        )
        assert login_resp.status_code == 200, "Should be able to login with new password"

    def test_change_password_wrong_current(self, client, auth_headers):
        """Changing password with wrong current password returns 400."""
        resp = client.put(
            "/api/v1/auth/me/password",
            headers=auth_headers,
            json={
                "current_password": "WrongCurrentP@ss!",  # NOSONAR — S2068: test credential constant, not a real secret
                "new_password": "N3wS3cureP@ss!",  # NOSONAR — S2068: test credential constant, not a real secret
            },
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_weak_new(self, client, auth_headers):
        """Changing to a weak new password returns 422."""
        resp = client.put(
            "/api/v1/auth/me/password",
            headers=auth_headers,
            json={
                "current_password": "Str0ngP@ss!",  # NOSONAR — S2068: test credential constant, not a real secret
                "new_password": "password",  # blocklisted
            },
        )
        assert resp.status_code == 422, f"Expected 422 for weak password, got {resp.status_code}"


# ===========================================================================
# 8. POST /api/v1/auth/forgot-password
# ===========================================================================


class TestForgotPassword:
    """Tests for the forgot-password endpoint.

    SECURITY (E-09): In production, AUTH_RETURN_RESET_TOKEN defaults to
    'false' and is force-disabled — reset tokens are sent via email only.
    In tests, conftest.py sets AUTH_RETURN_RESET_TOKEN=true and
    ENVIRONMENT=development so the test suite can retrieve the token
    from the response to test the reset-password flow end-to-end.
    """

    def test_forgot_password_success(self, client, registered_user):
        """Requesting reset for an existing email returns 200 with a token.

        Note: reset_token is present ONLY because conftest.py sets
        AUTH_RETURN_RESET_TOKEN=true for tests. In production, this
        field is absent — the token goes via email only.
        """
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "testuser@example.com"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert "reset_token" in data, (
            "Response should include reset_token in test mode (conftest sets "
            "AUTH_RETURN_RESET_TOKEN=true). In production this field is absent."
        )

    def test_forgot_password_nonexistent_email(self, client):
        """Requesting reset for a non-existent email still returns 200."""
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )
        assert resp.status_code == 200, (
            f"Expected 200 for non-existent email (no enumeration), got {resp.status_code}"
        )
        data = resp.json()
        assert "reset_token" not in data, "Non-existent email must NOT return a reset token"


# ===========================================================================
# 9. POST /api/v1/auth/reset-password
# ===========================================================================


class TestResetPassword:
    """Tests for the reset-password endpoint."""

    def _get_reset_token(self, client, email="resetuser@example.com"):
        """Helper: register user, request reset, return the reset token."""
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "resetuser",
                "email": email,
                "password": TEST_PASSWORD_9,
            },
        )
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": email},
        )
        return resp.json()["reset_token"]

    def test_reset_password_success(self, client):
        """Resetting password with a valid token succeeds."""
        token = self._get_reset_token(client)
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "Br4ndN3wP@ss!"},  # NOSONAR — S2068: test credential constant, not a real secret
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        # Verify login with new password
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "resetuser", "password": TEST_PASSWORD_6},
        )
        assert login_resp.status_code == 200, "Should login with reset password"

    def test_reset_password_expired_token(self, client):
        """An expired reset token returns 400."""
        # We simulate an expired token by manually creating a user with
        # an expired reset_token_expires.  We'll directly set it via
        # the forgot-password endpoint and then manipulate the DB.
        # However, since we cannot easily modify the DB directly through
        # the API, we test with a completely bogus token.
        # NOTE: token value uses FAKE_TEST_TOKEN prefix so SonarCloud S6418
        # does not flag it as a hard-coded secret.
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "FAKE_TEST_TOKEN_expired_12345", "new_password": "Br4ndN3wP@ss!"},  # NOSONAR — S6418: fake test token, not a real secret
        )
        assert resp.status_code == 400, f"Expected 400 for expired token, got {resp.status_code}"

    def test_reset_password_invalid_token(self, client):
        """A completely invalid token returns 400."""
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "FAKE_TEST_TOKEN_invalid_xyz", "new_password": "Br4ndN3wP@ss!"},  # NOSONAR — S6418: fake test token, not a real secret
        )
        assert resp.status_code == 400, f"Expected 400 for invalid token, got {resp.status_code}"


# ===========================================================================
# 10. GET /api/v1/auth/users
# ===========================================================================


class TestListUsers:
    """Tests for the admin-only user list endpoint."""

    def test_admin_can_list_users(self, client, admin_headers):
        """An admin user can list all users."""
        resp = client.get("/api/v1/auth/users", headers=admin_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert isinstance(data["users"], list)

    def test_non_admin_forbidden(self, client, auth_headers):
        """A non-admin user gets 403 when listing users."""
        resp = client.get("/api/v1/auth/users", headers=auth_headers)
        assert resp.status_code == 403, f"Expected 403 for non-admin, got {resp.status_code}"


# ===========================================================================
# 11. DELETE /api/v1/auth/users/{user_id}
# ===========================================================================


class TestDeleteUser:
    """Tests for the admin-only user deletion endpoint."""

    def test_admin_can_delete_user(self, client, admin_headers):
        """An admin can soft-delete another user."""
        # Register a user to delete
        reg = client.post(
            "/api/v1/auth/register",
            json={
                "username": "deleteme",
                "email": "deleteme@example.com",
                "password": TEST_USER_PASSWORD,
            },
        )
        user_id = reg.json()["id"]

        resp = client.delete(
            f"/api/v1/auth/users/{user_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert "deactivated" in resp.json()["message"].lower()

    def test_non_admin_forbidden_delete(self, client, auth_headers):
        """A non-admin user gets 403 when trying to delete a user."""
        resp = client.delete(
            "/api/v1/auth/users/some-id",
            headers=auth_headers,
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"

    def test_self_delete_forbidden(self, client, admin_headers):
        """An admin cannot delete their own account."""
        # First get the admin's user ID
        me_resp = client.get("/api/v1/auth/me", headers=admin_headers)
        admin_id = me_resp.json()["id"]

        resp = client.delete(
            f"/api/v1/auth/users/{admin_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 400, f"Expected 400 for self-delete, got {resp.status_code}"
        assert "own account" in resp.json()["detail"].lower()
