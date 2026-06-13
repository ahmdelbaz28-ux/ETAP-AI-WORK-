"""acp.security — Authentication, authorization, and audit logging.

The security layer sits between the Transport layer and the Router layer.
It provides:

    * Token-based authentication (HMAC-SHA256 bearer tokens, pluggable validators)
    * Caller identity with scope extraction
    * Append-only structured audit logging (NDJSON)

Typical usage::

    from acp.security import AuthConfig, HmacTokenValidator, NDJSONAuditLogger
    from acp.router import Router, RouterConfig

    auth = HmacTokenValidator(AuthConfig(secret_key="secret"))
    audit = NDJSONAuditLogger("/var/log/acp/audit.ndjson")
    router = Router(
        runtime,
        RouterConfig(
            caller_scopes={"math.read"},
            auth_validator=auth.validate,
            audit_logger=audit,
        ),
    )
"""
from __future__ import annotations

from acp.security.audit import (
    AuditEntry,
    AuditLogger,
    InMemoryAuditLogger,
    NDJSONAuditLogger,
)
from acp.security.auth import (
    AuthConfig,
    AuthValidator,
    CallerIdentity,
    HmacTokenValidator,
    extract_token_from_header,
    validate_bearer_token,
)

__all__ = [
    "CallerIdentity",
    "AuthConfig",
    "AuthValidator",
    "HmacTokenValidator",
    "validate_bearer_token",
    "extract_token_from_header",
    "AuditEntry",
    "AuditLogger",
    "InMemoryAuditLogger",
    "NDJSONAuditLogger",
]
