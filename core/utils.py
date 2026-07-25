"""
core/utils.py — Shared utility functions used across the ETAP-AI-WORK codebase.

This module consolidates small helper functions that were previously duplicated
across multiple modules (identified by the duplicate-functions audit).

Functions:
    env_truthy(var, default) — Read a boolean from an environment variable.
                               Replaces ``integrations.langfuse_integration._env_truthy``
                               and ``acp_runtime.acp.config.env_bool``.
"""
from __future__ import annotations

import os


def env_truthy(var: str, default: bool = False) -> bool:
    """Read a boolean from an environment variable, or return the default.

    Returns True if the env var value (lowercased) is one of:
    ``"1"``, ``"true"``, ``"yes"``, ``"on"``.
    Returns False if the value is any other non-empty string.
    Returns ``default`` if the variable is not set (None).

    Parameters
    ----------
    var : str
        Environment variable name to read.
    default : bool
        Value to return when the variable is not set.

    Examples
    --------
    >>> env_truthy("LANGFUSE_ENABLED", default=True)   # var not set → True
    >>> env_truthy("DEBUG_MODE", default=False)         # var="1" → True
    >>> env_truthy("VERBOSE", default=False)             # var="no" → False
    """
    val = os.environ.get(var)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")
