"""
api/error_debugger.py — Structured error debugging and recovery module.

Provides:
  * Custom exception classes with unique error codes
  * Error-code mapping (each type gets a code like ERR_STUDY_001)
  * Error-context builder (captures request details, stack trace, environment)
  * Error-recovery suggestions (maps error codes to suggested fixes)
  * Error-report generator (JSON format for API responses)
  * Structured logging formatter with trace IDs

Integration with the engineering service::

    from api.error_debugger import (
        StudyExecutionError,
        ErrorContextBuilder,
        ErrorReportGenerator,
        StructuredFormatter,
    )
"""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Error-code registry
# ---------------------------------------------------------------------------

class ErrorCategory(str, Enum):
    """Top-level error category."""

    STUDY = "STUDY"
    VALIDATION = "VALIDATION"
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    DATABASE = "DATABASE"
    INTEGRATION = "INTEGRATION"
    SYSTEM = "SYSTEM"
    NETWORK = "NETWORK"


@dataclass(frozen=True)
class ErrorCode:
    """Structured error code with category, numeric ID, and human label."""

    code: str          # e.g. "ERR_STUDY_001"
    category: ErrorCategory
    numeric: int
    label: str
    http_status: int = 500


# ---------------------------------------------------------------------------
# Error-code definitions
# ---------------------------------------------------------------------------

ERR_STUDY_001 = ErrorCode(
    code="ERR_STUDY_001",
    category=ErrorCategory.STUDY,
    numeric=1,
    label="Study execution failed",
    http_status=500,
)
ERR_STUDY_002 = ErrorCode(
    code="ERR_STUDY_002",
    category=ErrorCategory.STUDY,
    numeric=2,
    label="Study type not supported",
    http_status=400,
)
ERR_STUDY_003 = ErrorCode(
    code="ERR_STUDY_003",
    category=ErrorCategory.STUDY,
    numeric=3,
    label="Study parameter validation failed",
    http_status=422,
)
ERR_STUDY_004 = ErrorCode(
    code="ERR_STUDY_004",
    category=ErrorCategory.STUDY,
    numeric=4,
    label="Study timed out",
    http_status=504,
)
ERR_STUDY_005 = ErrorCode(
    code="ERR_STUDY_005",
    category=ErrorCategory.STUDY,
    numeric=5,
    label="ETAP provider unavailable",
    http_status=503,
)
ERR_STUDY_006 = ErrorCode(
    code="ERR_STUDY_006",
    category=ErrorCategory.STUDY,
    numeric=6,
    label="Motor starting analysis not dispatched",
    http_status=501,
)
ERR_STUDY_007 = ErrorCode(
    code="ERR_STUDY_007",
    category=ErrorCategory.STUDY,
    numeric=7,
    label="Harmonic analysis not dispatched",
    http_status=501,
)
ERR_STUDY_008 = ErrorCode(
    code="ERR_STUDY_008",
    category=ErrorCategory.STUDY,
    numeric=8,
    label="Optimal power flow not dispatched",
    http_status=501,
)

ERR_VALIDATION_001 = ErrorCode(
    code="ERR_VALIDATION_001",
    category=ErrorCategory.VALIDATION,
    numeric=1,
    label="System validation failed",
    http_status=400,
)
ERR_VALIDATION_002 = ErrorCode(
    code="ERR_VALIDATION_002",
    category=ErrorCategory.VALIDATION,
    numeric=2,
    label="Input sanitization blocked malicious content",
    http_status=400,
)
ERR_VALIDATION_003 = ErrorCode(
    code="ERR_VALIDATION_003",
    category=ErrorCategory.VALIDATION,
    numeric=3,
    label="Missing required field",
    http_status=422,
)

ERR_AUTH_001 = ErrorCode(
    code="ERR_AUTH_001",
    category=ErrorCategory.AUTH,
    numeric=1,
    label="Missing or invalid API key",
    http_status=401,
)
ERR_AUTH_002 = ErrorCode(
    code="ERR_AUTH_002",
    category=ErrorCategory.AUTH,
    numeric=2,
    label="JWT token expired",
    http_status=401,
)
ERR_AUTH_003 = ErrorCode(
    code="ERR_AUTH_003",
    category=ErrorCategory.AUTH,
    numeric=3,
    label="Insufficient permissions (RBAC/ABAC denied)",
    http_status=403,
)
ERR_AUTH_004 = ErrorCode(
    code="ERR_AUTH_004",
    category=ErrorCategory.AUTH,
    numeric=4,
    label="MFA verification failed",
    http_status=401,
)

ERR_RATE_LIMIT_001 = ErrorCode(
    code="ERR_RATE_LIMIT_001",
    category=ErrorCategory.RATE_LIMIT,
    numeric=1,
    label="Rate limit exceeded",
    http_status=429,
)

ERR_DATABASE_001 = ErrorCode(
    code="ERR_DATABASE_001",
    category=ErrorCategory.DATABASE,
    numeric=1,
    label="Database connection failed",
    http_status=503,
)
ERR_DATABASE_002 = ErrorCode(
    code="ERR_DATABASE_002",
    category=ErrorCategory.DATABASE,
    numeric=2,
    label="Database query failed",
    http_status=500,
)
ERR_DATABASE_003 = ErrorCode(
    code="ERR_DATABASE_003",
    category=ErrorCategory.DATABASE,
    numeric=3,
    label="Database migration error",
    http_status=500,
)

ERR_INTEGRATION_001 = ErrorCode(
    code="ERR_INTEGRATION_001",
    category=ErrorCategory.INTEGRATION,
    numeric=1,
    label="ETAP COM automation unavailable",
    http_status=503,
)
ERR_INTEGRATION_002 = ErrorCode(
    code="ERR_INTEGRATION_002",
    category=ErrorCategory.INTEGRATION,
    numeric=2,
    label="GIS provider unavailable",
    http_status=503,
)
ERR_INTEGRATION_003 = ErrorCode(
    code="ERR_INTEGRATION_003",
    category=ErrorCategory.INTEGRATION,
    numeric=3,
    label="SCADA data source unavailable",
    http_status=503,
)
ERR_INTEGRATION_004 = ErrorCode(
    code="ERR_INTEGRATION_004",
    category=ErrorCategory.INTEGRATION,
    numeric=4,
    label="Digital twin synchronization failed",
    http_status=503,
)

ERR_SYSTEM_001 = ErrorCode(
    code="ERR_SYSTEM_001",
    category=ErrorCategory.SYSTEM,
    numeric=1,
    label="Internal server error",
    http_status=500,
)
ERR_SYSTEM_002 = ErrorCode(
    code="ERR_SYSTEM_002",
    category=ErrorCategory.SYSTEM,
    numeric=2,
    label="Memory limit exceeded",
    http_status=507,
)
ERR_SYSTEM_003 = ErrorCode(
    code="ERR_SYSTEM_003",
    category=ErrorCategory.SYSTEM,
    numeric=3,
    label="Configuration error",
    http_status=500,
)

ERR_NETWORK_001 = ErrorCode(
    code="ERR_NETWORK_001",
    category=ErrorCategory.NETWORK,
    numeric=1,
    label="Upstream service timeout",
    http_status=504,
)
ERR_NETWORK_002 = ErrorCode(
    code="ERR_NETWORK_002",
    category=ErrorCategory.NETWORK,
    numeric=2,
    label="Connection refused",
    http_status=502,
)


# Full registry for lookups
_ERROR_CODE_REGISTRY: Dict[str, ErrorCode] = {
    ec.code: ec
    for ec in [
        ERR_STUDY_001, ERR_STUDY_002, ERR_STUDY_003, ERR_STUDY_004,
        ERR_STUDY_005, ERR_STUDY_006, ERR_STUDY_007, ERR_STUDY_008,
        ERR_VALIDATION_001, ERR_VALIDATION_002, ERR_VALIDATION_003,
        ERR_AUTH_001, ERR_AUTH_002, ERR_AUTH_003, ERR_AUTH_004,
        ERR_RATE_LIMIT_001,
        ERR_DATABASE_001, ERR_DATABASE_002, ERR_DATABASE_003,
        ERR_INTEGRATION_001, ERR_INTEGRATION_002, ERR_INTEGRATION_003,
        ERR_INTEGRATION_004,
        ERR_SYSTEM_001, ERR_SYSTEM_002, ERR_SYSTEM_003,
        ERR_NETWORK_001, ERR_NETWORK_002,
    ]
}


def lookup_error_code(code: str) -> Optional[ErrorCode]:
    """Look up an :class:`ErrorCode` by its string code.

    Args:
        code: Error code string, e.g. ``"ERR_STUDY_001"``.

    Returns:
        The matching :class:`ErrorCode`, or ``None`` if not found.
    """
    return _ERROR_CODE_REGISTRY.get(code)


# ---------------------------------------------------------------------------
# Custom exception classes
# ---------------------------------------------------------------------------

class ETAPPlatformError(Exception):
    """Base exception for all ETAP AI Platform errors.

    Every subclass carries an :class:`ErrorCode` and optional context.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ERR_SYSTEM_001,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.trace_id = trace_id or str(uuid.uuid4())
        self.cause = cause
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        result = {
            "error_code": self.error_code.code,
            "category": self.error_code.category.value,
            "label": self.error_code.label,
            "message": self.message,
            "http_status": self.error_code.http_status,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "context": self.context,
        }
        if self.cause:
            result["cause"] = str(self.cause)
        return result


class StudyExecutionError(ETAPPlatformError):
    """Raised when a power-system study fails to execute.

    Covers engine errors, missing dispatchers, ETAP provider failures,
    timeouts, and invalid study parameters.
    """

    def __init__(
        self,
        message: str,
        study_type: Optional[str] = None,
        error_code: ErrorCode = ERR_STUDY_001,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        ctx = context or {}
        if study_type:
            ctx["study_type"] = study_type
        super().__init__(
            message=message,
            error_code=error_code,
            context=ctx,
            trace_id=trace_id,
            cause=cause,
        )
        self.study_type = study_type


class SystemValidationError(ETAPPlatformError):
    """Raised when a power-system model fails validation.

    Covers structural errors (missing slack bus, unknown bus
    references), electrical constraint violations, and input
    sanitization blocks.
    """

    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[str]] = None,
        error_code: ErrorCode = ERR_VALIDATION_001,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        ctx = context or {}
        if validation_errors:
            ctx["validation_errors"] = validation_errors
        super().__init__(
            message=message,
            error_code=error_code,
            context=ctx,
            trace_id=trace_id,
            cause=cause,
        )
        self.validation_errors = validation_errors or []


class AuthenticationError(ETAPPlatformError):
    """Raised when authentication fails.

    Covers missing/invalid API keys, expired JWTs, MFA failures,
    and ABAC/RBAC denials.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ERR_AUTH_001,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            trace_id=trace_id,
            cause=cause,
        )


class RateLimitError(ETAPPlatformError):
    """Raised when a client exceeds the rate limit.

    Includes ``retry_after_sec`` for the ``Retry-After`` header.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after_sec: int = 60,
        error_code: ErrorCode = ERR_RATE_LIMIT_001,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        ctx = context or {}
        ctx["retry_after_sec"] = retry_after_sec
        super().__init__(
            message=message,
            error_code=error_code,
            context=ctx,
            trace_id=trace_id,
            cause=cause,
        )
        self.retry_after_sec = retry_after_sec


class DatabaseError(ETAPPlatformError):
    """Raised when a database operation fails.

    Covers connection failures, query errors, and migration issues.
    """

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ERR_DATABASE_001,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        cause: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            trace_id=trace_id,
            cause=cause,
        )


# ---------------------------------------------------------------------------
# Error-context builder
# ---------------------------------------------------------------------------

class ErrorContextBuilder:
    """Build a rich error-context dictionary for debugging.

    Captures request details, stack trace, environment info, and any
    custom context provided by the caller.

    Example::

        builder = ErrorContextBuilder(request=my_fastapi_request)
        ctx = builder.build()
        # ctx = {"request": {...}, "stack_trace": "...", "environment": {...}, ...}
    """

    def __init__(
        self,
        request: Any = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the context builder.

        Args:
            request: A FastAPI/Starlette ``Request`` object (optional).
            extra: Additional key-value pairs to include in the context.
        """
        self._request = request
        self._extra = extra or {}

    async def build(self) -> Dict[str, Any]:
        """Build the full error context dictionary.

        Returns:
            A dictionary suitable for inclusion in an error report.
        """
        ctx: Dict[str, Any] = {}

        # Request details
        if self._request is not None:
            ctx["request"] = await self._extract_request_info(self._request)

        # Stack trace
        ctx["stack_trace"] = self._extract_stack_trace()

        # Environment info
        ctx["environment"] = self._extract_environment()

        # Extra context
        if self._extra:
            ctx["custom"] = self._extra

        return ctx

    def build_sync(self) -> Dict[str, Any]:
        """Synchronous version of :meth:`build`.

        Note: request details may be incomplete if the request body
        needs to be read asynchronously.
        """
        ctx: Dict[str, Any] = {}

        if self._request is not None:
            ctx["request"] = self._extract_request_info_sync(self._request)

        ctx["stack_trace"] = self._extract_stack_trace()
        ctx["environment"] = self._extract_environment()

        if self._extra:
            ctx["custom"] = self._extra

        return ctx

    @staticmethod
    async def _extract_request_info(request: Any) -> Dict[str, Any]:
        """Extract relevant details from a FastAPI Request object."""
        info: Dict[str, Any] = {
            "method": getattr(request, "method", "UNKNOWN"),
            "url": str(getattr(request, "url", "UNKNOWN")),
            "path": str(getattr(request.url, "path", "UNKNOWN")) if hasattr(request, "url") else "UNKNOWN",
            "query_params": dict(getattr(request, "query_params", {})),
            "headers": {},
            "client_ip": None,
            "trace_id": None,
        }

        # Sanitize headers (remove sensitive values)
        sensitive_headers = {"authorization", "x-api-key", "cookie"}
        headers = getattr(request, "headers", {})
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                info["headers"][key] = "***REDACTED***"
            else:
                info["headers"][key] = value

        # Client IP
        client = getattr(request, "client", None)
        if client:
            info["client_ip"] = getattr(client, "host", None)

        # Trace ID from state
        state = getattr(request, "state", None)
        if state and hasattr(state, "trace_id"):
            info["trace_id"] = state.trace_id

        # Request body (only for POST/PUT/PATCH, limited size)
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.body()
                body_str = body.decode("utf-8", errors="replace")[:2048]
                # Redact potential secrets in the body
                info["body_preview"] = _redact_secrets(body_str)
            except Exception:
                info["body_preview"] = "<unable to read>"

        return info

    @staticmethod
    def _extract_request_info_sync(request: Any) -> Dict[str, Any]:
        """Synchronous version of request info extraction."""
        info: Dict[str, Any] = {
            "method": getattr(request, "method", "UNKNOWN"),
            "url": str(getattr(request, "url", "UNKNOWN")),
            "path": str(getattr(request.url, "path", "UNKNOWN")) if hasattr(request, "url") else "UNKNOWN",
            "client_ip": None,
        }

        client = getattr(request, "client", None)
        if client:
            info["client_ip"] = getattr(client, "host", None)

        return info

    @staticmethod
    def _extract_stack_trace() -> str:
        """Extract the current stack trace as a string."""
        return "".join(traceback.format_stack())

    @staticmethod
    def _extract_environment() -> Dict[str, Any]:
        """Extract environment and platform information."""
        return {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "hostname": platform.node(),
            "pid": os.getpid(),
            "environment": os.environ.get("ENVIRONMENT", os.environ.get("ENV", "development")),
            "engine_version": os.environ.get("ENGINEERING_SERVICE_VERSION", "1.0.0"),
        }


def _redact_secrets(text: str) -> str:
    """Redact potential secrets from a string.

    Replaces values that look like API keys, tokens, or passwords
    with ``***REDACTED***``.
    """
    patterns = [
        (r'(api[_-]?key["\s:=]+)["\']?[\w\-]{8,}["\']?', r'\1***REDACTED***'),
        (r'(token["\s:=]+)["\']?[\w\-\.]{8,}["\']?', r'\1***REDACTED***'),
        (r'(password["\s:=]+)["\']?[\w\-]{4,}["\']?', r'\1***REDACTED***'),
        (r'(secret["\s:=]+)["\']?[\w\-]{8,}["\']?', r'\1***REDACTED***'),
        (r'(bearer\s+)[\w\-\.]+', r'\1***REDACTED***'),
    ]

    result = text
    for pattern, replacement in patterns:
        import re
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


# ---------------------------------------------------------------------------
# Error-recovery suggestions
# ---------------------------------------------------------------------------

_RECOVERY_SUGGESTIONS: Dict[str, List[Dict[str, str]]] = {
    ERR_STUDY_001.code: [
        {
            "action": "retry",
            "description": "Retry the study request. Transient engine errors may resolve on retry.",
        },
        {
            "action": "check_system_model",
            "description": "Verify the system model is valid using POST /api/v1/system/validate.",
        },
        {
            "action": "check_logs",
            "description": "Check engineering_service logs for the full stack trace.",
        },
    ],
    ERR_STUDY_002.code: [
        {
            "action": "check_study_type",
            "description": "Verify study_type is one of the supported values: load_flow, short_circuit, fault, arc_flash, protection_coordination, coordination, motor_starting, harmonic_analysis, optimal_power_flow.",
        },
    ],
    ERR_STUDY_003.code: [
        {
            "action": "check_parameters",
            "description": "Review study parameters against the expected schema for the study type.",
        },
        {
            "action": "validate_system",
            "description": "Use POST /api/v1/system/validate to verify the system model.",
        },
    ],
    ERR_STUDY_004.code: [
        {
            "action": "reduce_complexity",
            "description": "The study timed out. Try reducing system size or simplifying parameters.",
        },
        {
            "action": "increase_timeout",
            "description": "Set ENGINEERING_SERVICE_REQUEST_TIMEOUT to a higher value.",
        },
    ],
    ERR_STUDY_005.code: [
        {
            "action": "check_etap_service",
            "description": "Verify the ETAP worker service is running and accessible.",
        },
        {
            "action": "fallback_native",
            "description": "Retry with use_etap=False to use the native engine instead.",
        },
    ],
    ERR_STUDY_006.code: [
        {
            "action": "implement_dispatcher",
            "description": "The motor_starting dispatcher is not implemented in the engine. Implement PowerSystemEngine.run_motor_starting().",
        },
        {
            "action": "use_etap",
            "description": "Use the ETAP provider with study_type=etap_motor_starting instead.",
        },
    ],
    ERR_STUDY_007.code: [
        {
            "action": "implement_dispatcher",
            "description": "The harmonic_analysis dispatcher is not implemented in the engine. Implement PowerSystemEngine.run_harmonic_analysis().",
        },
        {
            "action": "use_etap",
            "description": "Use the ETAP provider with study_type=etap_harmonic_analysis instead.",
        },
    ],
    ERR_STUDY_008.code: [
        {
            "action": "implement_dispatcher",
            "description": "The optimal_power_flow dispatcher is not implemented in the engine. Implement PowerSystemEngine.run_optimal_power_flow().",
        },
        {
            "action": "use_etap",
            "description": "Use the ETAP provider with study_type=etap_optimal_power_flow instead.",
        },
    ],
    ERR_VALIDATION_001.code: [
        {
            "action": "fix_validation_errors",
            "description": "Address the validation errors listed in the response and resubmit.",
        },
    ],
    ERR_AUTH_001.code: [
        {
            "action": "provide_api_key",
            "description": "Include a valid X-API-Key header in the request.",
        },
        {
            "action": "check_key_configuration",
            "description": "If developing locally, set ENGINEERING_SERVICE_AUTH_DISABLED=true.",
        },
    ],
    ERR_AUTH_002.code: [
        {
            "action": "refresh_token",
            "description": "Use the refresh token endpoint to obtain a new access token.",
        },
    ],
    ERR_AUTH_003.code: [
        {
            "action": "check_permissions",
            "description": "Verify the user has the required role/permissions for this action.",
        },
    ],
    ERR_RATE_LIMIT_001.code: [
        {
            "action": "wait_and_retry",
            "description": "Wait for the Retry-After period and retry the request.",
        },
        {
            "action": "reduce_request_rate",
            "description": "Implement client-side rate limiting to avoid hitting the server limit.",
        },
    ],
    ERR_DATABASE_001.code: [
        {
            "action": "check_database_url",
            "description": "Verify the DATABASE_URL environment variable points to a valid database.",
        },
        {
            "action": "check_disk_space",
            "description": "For SQLite, ensure the data directory exists and has write permissions.",
        },
    ],
    ERR_INTEGRATION_001.code: [
        {
            "action": "check_etap_worker",
            "description": "Verify the ETAP worker service is running on Windows with ETAP installed.",
        },
    ],
    ERR_INTEGRATION_002.code: [
        {
            "action": "check_gis_provider",
            "description": "Verify the GIS provider (QGIS/ArcGIS) is accessible and configured.",
        },
    ],
}


def get_recovery_suggestions(error_code: str) -> List[Dict[str, str]]:
    """Look up recovery suggestions for an error code.

    Args:
        error_code: The error code string, e.g. ``"ERR_STUDY_001"``.

    Returns:
        A list of suggestion dictionaries with ``action`` and
        ``description`` keys.
    """
    return _RECOVERY_SUGGESTIONS.get(error_code, [
        {
            "action": "check_logs",
            "description": "Check the service logs for more details about this error.",
        },
        {
            "action": "contact_support",
            "description": "If the error persists, contact the platform support team.",
        },
    ])


# ---------------------------------------------------------------------------
# Error-report generator
# ---------------------------------------------------------------------------

@dataclass
class ErrorReport:
    """Structured error report suitable for API responses.

    Contains all relevant details for client-side error handling,
    debugging, and user-facing messages.
    """

    error_code: str
    category: str
    label: str
    message: str
    http_status: int
    trace_id: str
    timestamp: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_suggestions: List[Dict[str, str]] = field(default_factory=list)
    request_id: Optional[str] = None
    documentation_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        result = {
            "error_code": self.error_code,
            "category": self.category,
            "label": self.label,
            "message": self.message,
            "http_status": self.http_status,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "context": self.context,
            "recovery_suggestions": self.recovery_suggestions,
        }
        if self.request_id:
            result["request_id"] = self.request_id
        if self.documentation_url:
            result["documentation_url"] = self.documentation_url
        return result

    def to_json(self, indent: int = 2) -> str:
        """Serialize the report to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


class ErrorReportGenerator:
    """Generate structured :class:`ErrorReport` objects.

    Can build reports from custom exceptions, raw error codes, or
    unexpected exceptions.

    Example::

        generator = ErrorReportGenerator()
        report = await generator.from_exception(
            exc=StudyExecutionError("Load flow diverged", study_type="load_flow"),
            request=my_request,
        )
        return JSONResponse(status_code=report.http_status, content=report.to_dict())
    """

    async def from_exception(
        self,
        exc: Exception,
        request: Any = None,
        trace_id: Optional[str] = None,
    ) -> ErrorReport:
        """Build an error report from an exception.

        Args:
            exc: The exception to report.
            request: The FastAPI request (optional, for context).
            trace_id: Override trace ID (defaults to UUID).

        Returns:
            A fully populated :class:`ErrorReport`.
        """
        if isinstance(exc, ETAPPlatformError):
            error_code = exc.error_code
            message = exc.message
            context = dict(exc.context)
            tid = trace_id or exc.trace_id
        else:
            error_code = ERR_SYSTEM_001
            message = str(exc) or "An unexpected error occurred"
            context = {}
            tid = trace_id or str(uuid.uuid4())

        # Build extra context from the request
        if request is not None:
            try:
                builder = ErrorContextBuilder(request=request)
                request_ctx = await builder.build()
                context["debug"] = request_ctx
            except Exception:
                pass  # Context building must not mask the original error

        # Look up recovery suggestions
        suggestions = get_recovery_suggestions(error_code.code)

        # Documentation URL
        doc_url = f"https://docs.etap-ai.dev/errors/{error_code.code.lower()}"

        return ErrorReport(
            error_code=error_code.code,
            category=error_code.category.value,
            label=error_code.label,
            message=message,
            http_status=error_code.http_status,
            trace_id=tid,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context,
            recovery_suggestions=suggestions,
            documentation_url=doc_url,
        )

    def from_error_code(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> ErrorReport:
        """Build an error report from an error code.

        Args:
            error_code: The :class:`ErrorCode` to report.
            message: Override message (defaults to the code's label).
            context: Additional context.
            trace_id: Override trace ID.

        Returns:
            A fully populated :class:`ErrorReport`.
        """
        suggestions = get_recovery_suggestions(error_code.code)
        doc_url = f"https://docs.etap-ai.dev/errors/{error_code.code.lower()}"

        return ErrorReport(
            error_code=error_code.code,
            category=error_code.category.value,
            label=error_code.label,
            message=message or error_code.label,
            http_status=error_code.http_status,
            trace_id=trace_id or str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            context=context or {},
            recovery_suggestions=suggestions,
            documentation_url=doc_url,
        )


# ---------------------------------------------------------------------------
# Structured logging formatter
# ---------------------------------------------------------------------------

class StructuredFormatter(logging.Formatter):
    """JSON-based structured log formatter with trace IDs.

    Outputs one JSON object per log line, making logs easily
    parseable by log aggregation systems (Loki, ELK, Datadog).

    Example output::

        {
            "timestamp": "2025-01-15T10:30:00Z",
            "level": "ERROR",
            "logger": "engineering_service",
            "trace_id": "abc-123",
            "message": "Study execution failed",
            "error_code": "ERR_STUDY_001",
            "module": "engineering_service",
            "function": "run_study",
            "line": 950
        }
    """

    def __init__(
        self,
        service_name: str = "engineering_service",
        version: str = "1.0.0",
    ) -> None:
        """Initialize the formatter.

        Args:
            service_name: Name of the service for log identification.
            version: Service version for log identification.
        """
        super().__init__()
        self.service_name = service_name
        self.version = version

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service_name,
            "version": self.version,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include trace_id if present
        trace_id = getattr(record, "trace_id", None)
        if trace_id:
            log_entry["trace_id"] = trace_id

        # Include error_code if present
        error_code = getattr(record, "error_code", None)
        if error_code:
            log_entry["error_code"] = error_code

        # Include extra fields
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields and isinstance(extra_fields, dict):
            log_entry.update(extra_fields)

        # Include exception info
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else "Unknown",
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        try:
            return json.dumps(log_entry, default=str)
        except (TypeError, ValueError):
            # Fallback to simple format if JSON serialization fails
            return (
                f"{log_entry.get('timestamp', '?')} "
                f"{log_entry.get('level', '?')} "
                f"[{log_entry.get('trace_id', '-')}] "
                f"{log_entry.get('message', '')}"
            )


def setup_structured_logging(
    service_name: str = "engineering_service",
    version: str = "1.0.0",
    level: int = logging.INFO,
) -> logging.Logger:
    """Configure structured JSON logging for the engineering service.

    Args:
        service_name: Name of the service.
        version: Service version.
        level: Logging level.

    Returns:
        The configured root logger for the service.
    """
    formatter = StructuredFormatter(service_name=service_name, version=version)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)

    return logger
