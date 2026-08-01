"""Router — JSON-RPC 2.0 dispatch layer.

Accepts raw Python dicts (already parsed from JSON), validates them as
ACP envelopes, enforces scope-based authorization, dispatches to the
Runtime engine, and returns JSON-RPC 2.0 response dicts.

The router is thin and stateless: all capability state lives in the
``AcpRuntime`` instance passed to the constructor.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Optional, Union

from pydantic import ValidationError

from acp.errors import (
    AcpError,
    AuthenticationRequired,
    CapabilityNotFound,
    ScopeNotPermitted,
)
from acp.router.scope import ScopeValidator
from acp.runtime import AcpRuntime
from acp.schema import JsonRpcError, JsonRpcNotification, JsonRpcRequest, JsonRpcResponse

__all__ = ["Router", "RouterConfig"]

# JSON-RPC 2.0 standard error codes
JSONRPC_PARSE_ERROR = -32700
JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603

# ACP error codes (already defined in acp.errors)
# -32001 DeadlineExceeded
# -32002 CapabilityNotFound
# -32003 ScopeNotPermitted
# -32004 HandlerError
# -32005 AuthenticationRequired
# -32006 RateLimitExceeded
# -32007 TransportClosed


# Type alias for an optional notification handler callback.
NotificationHandler = Optional[Callable[[dict], Any]]

# Type alias for auth validator (re-exported from security for convenience)
# Type alias for audit logger (re-exported from security for convenience)
from acp.security.audit import AuditLogger
from acp.security.auth import AuthValidator


class RouterConfig:
    """Lightweight configuration for a Router instance.

    Attributes:
        caller_scopes: set of scope strings the caller possesses.
        on_notification: optional async callback invoked for every
            notification that passes validation. The callback receives
            the validated notification as a dict.
        auth_validator: optional callable that validates a raw token
            string and returns a ``CallerIdentity``. If set, the router
            enforces authentication on every request.
        audit_logger: optional ``AuditLogger`` instance. If set, the
            router logs an audit entry for every request and every
            notification.
        require_auth_for_public: if True, even public capabilities
            (no required scopes) require a valid token. Default False.
        tracer: optional ``Tracer`` instance for distributed tracing.
        metrics: optional ``MetricsRegistry`` instance for metrics.
        logger: optional ``StructuredLogger`` instance for structured
            logging.
    """

    def __init__(
        self,
        caller_scopes: set[str] | None = None,
        *,
        on_notification: NotificationHandler = None,
        auth_validator: Optional[AuthValidator] = None,
        audit_logger: Optional[AuditLogger] = None,
        require_auth_for_public: bool = False,
        tracer: Optional[Any] = None,
        metrics: Optional[Any] = None,
        logger: Optional[Any] = None,
    ) -> None:
        self.caller_scopes = set(caller_scopes or ())
        self.on_notification = on_notification
        self.auth_validator = auth_validator
        self.audit_logger = audit_logger
        self.require_auth_for_public = require_auth_for_public
        self.tracer = tracer
        self.metrics = metrics
        self.logger = logger


class Router:
    """JSON-RPC 2.0 router with ACP scope validation + optional auth / audit.

    Parameters:
        runtime: the AcpRuntime instance that owns the capability registry.
        config: RouterConfig (scopes, notification callback, auth, audit).

    Usage::

        router = Router(runtime, RouterConfig(caller_scopes={"math.read"}))
        response_dict = await router.handle(incoming_dict)
    """

    def __init__(self, runtime: AcpRuntime, config: Optional[RouterConfig] = None) -> None:
        self._runtime = runtime
        self._config = config or RouterConfig()
        self._scope_validator = ScopeValidator(self._config.caller_scopes)
        self._log = logging.getLogger("acp.router")

    # ------------------------------------------------------------- public API

    async def handle(self, envelope: dict) -> Optional[dict]:
        """Accept a JSON-RPC envelope dict, return a response dict (or None).

        Args:
            envelope: a dict representing a JSON-RPC 2.0 request or
                notification. Usually obtained from ``json.loads`` on the
                transport layer.

        Returns:
            A JSON-RPC 2.0 response dict (for requests), or ``None`` (for
            notifications that pass validation).

        Raises:
            Nothing — all exceptions are caught and mapped to JSON-RPC
            error responses.
        """
        self._log.debug("handle envelope=%s", envelope.get("id", "<no-id>"))

        # Observability: record request count
        if self._config.metrics is not None:
            self._config.metrics.get_or_create_counter(
                "acp.router.requests.total",
                "Total requests",
            ).inc()

        # 1. Try request shape
        try:
            req = JsonRpcRequest.model_validate(envelope)
        except ValidationError:
            # 2. Try notification shape
            try:
                notif = JsonRpcNotification.model_validate(envelope)
            except ValidationError:
                # 3. Neither — invalid envelope
                if self._config.metrics is not None:
                    self._config.metrics.get_or_create_counter(
                        "acp.router.requests.invalid",
                        "Invalid requests",
                    ).inc()
                return self._error_response(
                    None,
                    JSONRPC_INVALID_REQUEST,
                    "Invalid JSON-RPC envelope",
                )
            return await self._handle_notification(notif)

        return await self._handle_request(req)

    # ----------------------------------------------------------- request path

    def _start_span(self, req: JsonRpcRequest) -> Optional[Any]:
        """Start an observability span for the request, if a tracer is configured."""
        if self._config.tracer is None:
            return None
        from acp.observability.tracer import TraceContext

        return self._config.tracer.start_span(
            "router.handle",
            TraceContext.from_trace_id(req.trace_id) if req.trace_id else None,
        )

    async def _authenticate(
        self, req: JsonRpcRequest
    ) -> tuple[str, ScopeValidator, Optional[tuple[int, str, Optional[Any]]]]:
        """Authenticate the request.

        Returns ``(caller_id, scope_validator, failure)`` where ``failure``
        is ``(code, message, data)`` or ``None`` when authentication
        succeeded (or no auth validator is configured).
        """
        if self._config.auth_validator is None:
            return "", self._scope_validator, None
        try:
            identity = self._config.auth_validator(req.trace_id)
            if hasattr(identity, "__await__"):
                identity = await identity  # type: ignore[operator]
            caller_id = identity.caller_id
            # Merge caller scopes from token with config scopes
            scope_validator = ScopeValidator(self._config.caller_scopes.union(identity.scopes))
        except AuthenticationRequired as e:
            return "", self._scope_validator, (AuthenticationRequired.code, e.message, e.data)
        except Exception as e:
            self._log.exception("auth validator failed for %s", req.id)
            return "", self._scope_validator, (AuthenticationRequired.code, f"Authentication failed: {e}", None)
        return caller_id, scope_validator, None

    async def _fail_request(
        self,
        req: JsonRpcRequest,
        span_ctx: Optional[Any],
        t0: float,
        code: int,
        message: str,
        data: Optional[Any] = None,
        *,
        caller_id: str = "",
        outcome: str = "error",
        audit_duration_ms: Optional[int] = None,
    ) -> dict:
        """Build an error response and finish observability.

        When ``audit_duration_ms`` is given the request is also audited
        with ``outcome``; ``0`` reproduces the auth-failure audit
        behaviour where no execution time is recorded.
        """
        resp = self._error_response(req.id, code, message, data)
        if audit_duration_ms is None:
            await self._finish_observability(span_ctx, t0, req, "error", code)
        else:
            await self._audit(
                req,
                caller_id=caller_id,
                outcome=outcome,
                error_code=code,
                duration_ms=audit_duration_ms,
            )
            await self._finish_observability(span_ctx, t0, req, outcome, code)
        return resp

    async def _execute_capability(
        self,
        req: JsonRpcRequest,
        _span_ctx: Optional[Any],  # S1172 param retained for interface consistency
        _t0: float,  # S1172 param retained for interface consistency
    ) -> tuple[dict, str, int]:
        """Dispatch the request; returns ``(response, outcome, error_code)``."""
        try:
            result = await self._runtime.execute(
                req.capability,
                req.params,
                trace_id=req.trace_id,
                deadline_ms=req.deadline_ms,
            )
            resp = self._success_response(req.id, result)
            outcome, error_code = "success", 0
        except AcpError as e:
            self._log.warning("acp error for %s: %s", req.id, e)
            resp = self._error_response(req.id, e.code, e.message, e.data)
            outcome, error_code = "error", e.code
        except Exception as e:
            self._log.exception("unexpected error for request %s", req.id)
            resp = self._error_response(req.id, JSONRPC_INTERNAL_ERROR, f"Internal error: {e}")
            outcome, error_code = "error", JSONRPC_INTERNAL_ERROR
        return resp, outcome, error_code

    async def _handle_request(
        self, req: JsonRpcRequest
    ) -> dict:
        """Validate, authenticate, authorize, dispatch, audit, and wrap the result."""
        t0 = time.perf_counter()
        caller_id = ""

        # Observability: start span
        span_ctx = self._start_span(req)

        # ---- params type check
        if req.params is not None and not isinstance(req.params, dict):
            return await self._fail_request(
                req,
                span_ctx,
                t0,
                JSONRPC_INVALID_PARAMS,
                "ACP params must be a dict (keyword arguments)",
            )

        # ---- authentication
        caller_id, scope_validator, auth_failure = await self._authenticate(req)
        if auth_failure is not None:
            code, message, data = auth_failure
            return await self._fail_request(
                req,
                span_ctx,
                t0,
                code,
                message,
                data,
                outcome="denied",
                audit_duration_ms=0,
            )

        # ---- capability exists
        meta = self._runtime.get_meta(req.capability)
        if meta is None:
            return await self._fail_request(
                req,
                span_ctx,
                t0,
                CapabilityNotFound.code,
                f"Capability {req.capability!r} is not registered",
                {"capability": req.capability, "available": self._runtime.capability_names},
                caller_id=caller_id,
                outcome="error",
                audit_duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        # ---- auth required for public?
        if self._config.require_auth_for_public and not caller_id:
            return await self._fail_request(
                req,
                span_ctx,
                t0,
                AuthenticationRequired.code,
                "Authentication required for all capabilities",
                caller_id=caller_id,
                outcome="denied",
                audit_duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        # ---- scope permission
        if not scope_validator.is_permitted(meta.scopes):
            return await self._fail_request(
                req,
                span_ctx,
                t0,
                ScopeNotPermitted.code,
                f"Scope not permitted for {req.capability!r}",
                {"capability": req.capability, "required_scopes": meta.scopes},
                caller_id=caller_id,
                outcome="denied",
                audit_duration_ms=int((time.perf_counter() - t0) * 1000),
            )

        # ---- execute
        resp, outcome, error_code = await self._execute_capability(req, span_ctx, t0)

        await self._audit(
            req,
            caller_id,
            outcome,
            error_code,
            int((time.perf_counter() - t0) * 1000),
        )
        await self._finish_observability(span_ctx, t0, req, outcome, error_code)
        return resp

    async def _finish_observability(  # S7503 async signature required by callers; body intentionally sync
        self,
        span_ctx: Optional[Any],
        t0: float,
        req: JsonRpcRequest,
        outcome: str,
        error_code: int,
    ) -> None:
        """Finish tracer span and record metrics."""
        duration_ms = int((time.perf_counter() - t0) * 1000)
        if self._config.metrics is not None:
            self._config.metrics.get_or_create_histogram(
                "acp.router.requests.duration_ms",
                "Request duration in milliseconds",
            ).observe(duration_ms)
            if outcome != "success":
                self._config.metrics.get_or_create_counter(
                    "acp.router.requests.errors",
                    "Request errors",
                ).inc()
        if self._config.tracer is not None and span_ctx is not None:
            from acp.observability.tracer import SpanStatus

            status = SpanStatus.OK if outcome == "success" else SpanStatus.ERROR
            self._config.tracer.finish_span(
                span_ctx,
                "router.handle",
                t0,
                status=status,
                tags={
                    "capability": req.capability,
                    "method": req.method,
                    "outcome": outcome,
                    "error_code": error_code,
                },
            )

    # ------------------------------------------------------- notification path

    async def _handle_notification(self, notif: JsonRpcNotification) -> None:
        """Validate and optionally forward a notification.

        Notifications are fire-and-forget: no response is returned.
        If an ``on_notification`` callback is configured, it is invoked
        with the validated notification dict.
        """
        self._log.debug("notification method=%s", notif.method)

        if self._config.on_notification is not None:
            try:
                await self._config.on_notification(notif.model_dump(mode="json"))
            except Exception:
                self._log.exception("notification callback failed for %s", notif.method)

        if self._config.audit_logger is not None:
            await self._config.audit_logger.log(
                method=notif.method,
                capability=notif.capability or "",
                outcome="notification",
                trace_id=notif.trace_id,
            )

        return None

    # -------------------------------------------------------- audit helper

    async def _audit(
        self,
        req: JsonRpcRequest,
        caller_id: str,
        outcome: str,
        error_code: int,
        duration_ms: int,
    ) -> None:
        if self._config.audit_logger is None:
            return
        await self._config.audit_logger.log(
            method=req.method,
            capability=req.capability,
            caller_id=caller_id,
            outcome=outcome,
            duration_ms=duration_ms,
            error_code=error_code,
            trace_id=req.trace_id,
        )

    # -------------------------------------------------------- response builders

    def _success_response(self, req_id: Any, result: Any) -> dict:
        return JsonRpcResponse(
            id=req_id,
            result=result,
        ).model_dump(mode="json")

    def _error_response(
        self,
        req_id: Any,
        code: int,
        message: str,
        data: Optional[dict] = None,
    ) -> dict:
        return JsonRpcResponse(
            id=req_id,
            error=JsonRpcError(code=code, message=message, data=data),
        ).model_dump(mode="json")
