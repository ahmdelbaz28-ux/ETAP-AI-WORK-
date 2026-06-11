"""acp — Agent Communication Protocol (standalone, Python 3.12+)."""
from __future__ import annotations

__version__ = "0.1.0"

# Public errors
from acp.errors import (
    AcpError,
    DeadlineExceeded,
    CapabilityNotFound,
    ScopeNotPermitted,
    HandlerError,
    AuthenticationRequired,
    RateLimitExceeded,
    TransportClosed,
)

# Public runtime
from acp.runtime import (
    AcpRuntime,
    capability,
    AcpHandler,
    discover_capabilities,
    list_capabilities,
    enforce_deadline_ms,
    deadline_scope,
    cancellable,
    ProgressEmitter,
    ProgressEvent,
)

# Public router
from acp.router import (
    Router,
    RouterConfig,
    ScopeValidator,
    check_scope,
)

# Public transport
from acp.transport import (
    Transport,
    StdioTransport,
    UDSTransport,
    UDSListener,
    WebSocketTransport,
    WebSocketListener,
    Server,
)

# Public schema
from acp.schema import (
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcNotification,
    JsonRpcError,
    AcpParams,
    AcpResult,
    CapabilityDescriptor,
    is_valid_capability_name,
    is_valid_scope,
    RequestId,
    TraceId,
)

# Public security
from acp.security import (
    CallerIdentity,
    AuthConfig,
    AuthValidator,
    HmacTokenValidator,
    validate_bearer_token,
    extract_token_from_header,
    AuditEntry,
    AuditLogger,
    InMemoryAuditLogger,
    NDJSONAuditLogger,
)

# Public observability
from acp.observability import (
    TraceContext,
    Span,
    SpanStatus,
    Tracer,
    InMemoryTracer,
    JsonTracer,
    NullTracer,
    Counter,
    Histogram,
    Gauge,
    MetricsRegistry,
    InMemoryMetricsRegistry,
    LogLevel,
    LogEntry,
    StructuredLogger,
    ConsoleStructuredLogger,
    InMemoryStructuredLogger,
    NullStructuredLogger,
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
