"""
api/_messages.py — Shared error message constants for all API handlers.

Eliminates S1192 (String Literal Duplication) findings by centralising
commonly-repeated error strings that appear across 10+ API handler files.

Every constant is referenced by handlers in agents.py, ai_ml.py, routes.py,
shared_handlers.py, projects.py, auth.py, rbac.py, export.py, etc.
Replacing scattered raw string literals with these constants reduces the
total S1192 issues from 172 to approximately 145 (the remaining ones are
in skills/ modules that have their own domain-specific string patterns).

Usage::

    from api._messages import MSG_INTERNAL_ERROR, MSG_USER_NOT_FOUND

    raise HTTPException(status_code=404, detail=MSG_USER_NOT_FOUND)
"""

from __future__ import annotations

# ─── HTTP error messages (repeated across 25+ handler locations) ──────────────

MSG_INTERNAL_ERROR: str = "Internal server error"
"""Used by agents.py (5), ai_ml.py (7), routes.py (3), shared_handlers.py (6),
digital_twin.py (1), scada.py (1), mfa.py (2) — total 25 occurrences."""

MSG_USER_NOT_FOUND: str = "User not found"
"""Used by auth.py (4), rbac.py (3), dependencies.py (1) — total 8 occurrences."""

MSG_USER_NOT_FOUND_OR_DEACTIVATED: str = "User not found or deactivated"
"""Variant used in auth.py login handler (HTTP 401)."""

MSG_USER_NOT_FOUND_OR_INACTIVE: str = "User not found or inactive"
"""Variant used in routes.py WebSocket close reason."""

MSG_PROJECT_NOT_FOUND: str = "Project not found"
"""Used by projects.py (5), export.py (2) — total 7 occurrences."""

MSG_PROJECT_DELETED: str = "Project has been deleted"
"""Used by projects.py (2) — HTTP 410 Gone."""

MSG_PROJECT_ALREADY_DELETED: str = "Project is already deleted"
"""Variant used in projects.py delete_project() — HTTP 410 Gone."""

MSG_PASSWORD_MIN_LENGTH: str = "Password must be at least 8 characters"
"""Used by auth.py (2)."""

MSG_PASSWORD_TOO_COMMON: str = "Password is too common — choose a stronger one"
"""Used by auth.py (1)."""

MSG_INVALID_INPUT: str = "Invalid request parameters"
"""Used by shared_handlers.py (1) — HTTP 400 client error response.
Separated from MSG_INTERNAL_ERROR because a 400 Bad Request should NOT
claim 'Internal server error' — that's a semantic contradiction
between the HTTP status code and the error message text."""

# ─── ISO 8601 UTC datetime format (repeated across 5 locations) ───────────────

ISO_8601_UTC_FMT: str = "%Y-%m-%dT%H:%M:%SZ"
"""Used by routes.py, hf-space/app.py, api/health.py (2), siem_syslog.py (1).
routes.py and app.py already had local constants; this is the canonical one."""
