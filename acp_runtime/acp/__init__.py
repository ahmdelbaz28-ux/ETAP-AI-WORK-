"""acp — Agent Communication Protocol (standalone, Python 3.12+)."""

from __future__ import annotations

__version__ = "0.1.0"

# Public errors
from acp.errors import (
    AcpError,
    AuthenticationRequired,
    CapabilityNotFound,
    DeadlineExceeded,
    HandlerError,
    RateLimitExceeded,
    ScopeNotPermitted,
    TransportClosed,
)

# Public observability
from acp.observability import (
    ConsoleStructuredLogger,
    Counter,
    Gauge,
    Histogram,
    InMemoryMetricsRegistry,
    InMemoryStructuredLogger,
    InMemoryTracer,
    JsonTracer,
    LogEntry,
    LogLevel,
    MetricsRegistry,
    NullStructuredLogger,
    NullTracer,
    Span,
    SpanStatus,
    StructuredLogger,
    TraceContext,
    Tracer,
)

# Public router
from acp.router import (
    Router,
    RouterConfig,
    ScopeValidator,
    check_scope,
)

# Public runtime
from acp.runtime import (
    AcpHandler,
    AcpRuntime,
    ProgressEmitter,
    ProgressEvent,
    cancellable,
    capability,
    deadline_scope,
    discover_capabilities,
    enforce_deadline_ms,
    list_capabilities,
)

# Public schema
from acp.schema import (
    AcpParams,
    AcpResult,
    CapabilityDescriptor,
    JsonRpcError,
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    RequestId,
    TraceId,
    is_valid_capability_name,
    is_valid_scope,
)

# Public security
from acp.security import (
    AuditEntry,
    AuditLogger,
    AuthConfig,
    AuthValidator,
    CallerIdentity,
    HmacTokenValidator,
    InMemoryAuditLogger,
    NDJSONAuditLogger,
    extract_token_from_header,
    validate_bearer_token,
)

# Public transport
from acp.transport import (
    Server,
    StdioTransport,
    Transport,
    UDSListener,
    UDSTransport,
    WebSocketListener,
    WebSocketTransport,
)

__all__ = [
    "__version__",
    # errors
    "AcpError",
    "DeadlineExceeded",
    "CapabilityNotFound",
    "ScopeNotPermitted",
    "HandlerError",
    "AuthenticationRequired",
    "RateLimitExceeded",
    "TransportClosed",
    # runtime
    "AcpRuntime",
    "capability",
    "AcpHandler",
    "discover_capabilities",
    "list_capabilities",
    "enforce_deadline_ms",
    "deadline_scope",
    "cancellable",
    "ProgressEmitter",
    "ProgressEvent",
    # router
    "Router",
    "RouterConfig",
    "ScopeValidator",
    "check_scope",
    # transport
    "Transport",
    "StdioTransport",
    "UDSTransport",
    "UDSListener",
    "WebSocketTransport",
    "WebSocketListener",
    "Server",
    # schema
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcNotification",
    "JsonRpcError",
    "AcpParams",
    "AcpResult",
    "CapabilityDescriptor",
    "is_valid_capability_name",
    "is_valid_scope",
    "RequestId",
    "TraceId",
    # security
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
    # observability
    "TraceContext",
    "Span",
    "SpanStatus",
    "Tracer",
    "InMemoryTracer",
    "JsonTracer",
    "NullTracer",
    "Counter",
    "Histogram",
    "Gauge",
    "MetricsRegistry",
    "InMemoryMetricsRegistry",
    "LogLevel",
    "LogEntry",
    "StructuredLogger",
    "ConsoleStructuredLogger",
    "InMemoryStructuredLogger",
    "NullStructuredLogger",
]
