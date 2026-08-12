"""
Environment classification helpers for authentication gating.

C-02 fix: ``ENGINEERING_SERVICE_AUTH_DISABLED=true`` must ONLY be honoured
in explicit development/test environments. Every request-time bypass re-checks
the environment through :func:`auth_disabled_allowed` (defense-in-depth), so a
misconfigured deployment (e.g. ``ENVIRONMENT=qa`` or an empty value) fails
closed instead of silently disabling authentication.
"""

from __future__ import annotations

import os

DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing", "ci"})

_PROD_ENVIRONMENTS = frozenset({"production", "prod", "staging"})


def get_environment() -> str:
    """Return the normalized environment name (default: ``development``)."""
    return os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")).lower()


def is_dev_environment() -> bool:
    """True only inside the explicit development/test allow-list."""
    return get_environment() in DEV_ENVIRONMENTS


def is_production_environment() -> bool:
    """True inside the explicit production allow-list."""
    return get_environment() in _PROD_ENVIRONMENTS


def auth_disabled_allowed() -> bool:
    """Whether the ``ENGINEERING_SERVICE_AUTH_DISABLED`` bypass may be honoured.

    Returns ``False`` when the variable is unset, OR when ``ENVIRONMENT``/``ENV``
    is missing (no implicit ``development`` default for the bypass), OR when the
    explicitly configured environment is not in the development allow-list.
    This is the fail-closed gate for C-02.
    """
    disabled = os.environ.get("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if not disabled:
        return False
    env = os.environ.get("ENVIRONMENT") or os.environ.get("ENV")
    if not env:
        return False
    return env.lower() in DEV_ENVIRONMENTS