"""Error handling and alerting infrastructure for the AhmedETAP Engineering Platform.

Provides production-grade error tracking, alerting, automatic recovery,
and a component guard context manager for standardized exception handling.
"""

from __future__ import annotations

import enum
import json
import logging
import smtplib
import threading
import time
import traceback
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from email.message import EmailMessage
from typing import Any, Optional, Union
from urllib.error import URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


class ErrorSeverity(enum.Enum):
    """Severity levels for system errors."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Error data model
# ---------------------------------------------------------------------------


@dataclass
class EngineSystemError:
    """Represents a single error event within the platform.

    Attributes:
        error_id: UUID string uniquely identifying this error.
        message: Human-readable error description.
        component: Source component name (e.g. ``load_flow``, ``etap_com``).
        severity: :class:`ErrorSeverity` level.
        timestamp: When the error occurred.
        details: Arbitrary key-value context payload.
        stack_trace: Captured stack trace, if available.
        user_id: Optional identifier of the user affected.
        acknowledged: Whether the error has been acknowledged.
        resolution: Optional resolution notes.
    """

    error_id: str
    message: str
    component: str
    severity: ErrorSeverity
    timestamp: datetime
    details: dict = field(default_factory=dict)
    stack_trace: str = ""
    user_id: Optional[str] = None
    acknowledged: bool = False
    resolution: Optional[str] = None


# Backward-compatible alias — maps SystemError to EngineSystemError so
# existing tests and code that import SystemError from this module continue
# to work.  New code should use EngineSystemError directly.
SystemError = EngineSystemError


# ---------------------------------------------------------------------------
# Alert manager
# ---------------------------------------------------------------------------


class AlertManager:
    """Manages real-time alert distribution across multiple channels.

    Channels
        * **Console** — always active; logs alerts via the ``alert`` logger.
        * **Email** — enabled after :meth:`configure_email` is called.
        * **Webhook** — enabled after :meth:`configure_webhook` is called.

    Alert rules can be registered via :meth:`add_alert_rule` to control which
    component/severity combinations trigger which channels.
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("alert")
        self._email_config: Optional[dict] = None
        self._webhook_config: Optional[dict] = None
        self._rules: list[dict] = []
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        email_status = "configured" if self._email_config else "not configured"
        return f"AlertManager(email={email_status}, rules={len(self._rules)})"

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure_email(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: list[str],
    ) -> None:
        """Configure SMTP email delivery for alerts.

        Args:
            smtp_server: SMTP hostname.
            smtp_port: SMTP port (typically 587 for TLS).
            username: Authentication username.
            password: Authentication password.
            from_addr: Sender email address.
            to_addrs: Recipient email addresses.
        """
        self._email_config = {
            "smtp_server": smtp_server,
            "smtp_port": smtp_port,
            "username": username,
            "password": password,
            "from_addr": from_addr,
            "to_addrs": to_addrs,
        }

    def configure_webhook(self, url: str, headers: Optional[dict] = None) -> None:
        """Configure a webhook URL for alert delivery.

        Args:
            url: Target URL (HTTP POST).
            headers: Optional HTTP headers.
        """
        self._webhook_config = {"url": url, "headers": headers or {}}

    def add_alert_rule(
        self,
        component: str,
        min_severity: ErrorSeverity,
        channels: list[str] | None = None,
    ) -> None:
        """Register an alert routing rule.

        When an error matches *component* and its severity is at or above
        *min_severity*, the rule fires on the listed *channels*.  Use ``*``
        as the component to match every component.

        Args:
            component: Component name or ``*`` for global.
            min_severity: Minimum severity to trigger the rule.
            channels: Channel list (e.g. ``["console", "email", "webhook"]``).
                      Defaults to all configured channels.
        """
        if channels is None:
            channels = ["console"]
        with self._lock:
            self._rules.append(
                {
                    "component": component,
                    "min_severity": min_severity,
                    "channels": channels,
                },
            )

    # ------------------------------------------------------------------
    # Alert dispatch
    # ------------------------------------------------------------------

    def trigger_alert(
        self,
        error: EngineSystemError,
        channels: list[str] | None = None,
    ) -> None:
        """Dispatch an alert for *error* through matching channels.

        If *channels* is provided it overrides rule-based routing and
        sends directly to those channels.

        Args:
            error: The error to alert on.
            channels: Optional explicit channel list (bypasses rules).
        """
        if channels is None:
            channels = self._resolve_channels(error)

        with self._lock:
            for ch in channels:
                if ch == "console":
                    self._alert_console(error)
                elif ch == "email":
                    self._alert_email(error)
                elif ch == "webhook":
                    self._alert_webhook(error)

    def get_active_alerts(self) -> list[EngineSystemError]:
        """Return errors that are currently active (unacknowledged CRITICAL/ERROR).

        This method is a **read-only** query — it relies on the caller having
        access to an ``ErrorHandler`` with the full history.  It returns an
        empty list here as a sentinel; errors must be queried from the handler.
        """
        return []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_channels(self, error: EngineSystemError) -> list[str]:
        """Collect channels whose rules match *error*."""
        matched: set[str] = set()
        severity_order = {
            ErrorSeverity.DEBUG: 0,
            ErrorSeverity.INFO: 1,
            ErrorSeverity.WARNING: 2,
            ErrorSeverity.ERROR: 3,
            ErrorSeverity.CRITICAL: 4,
        }
        error_level = severity_order[error.severity]
        with self._lock:
            for rule in self._rules:
                if rule["component"] != "*" and rule["component"] != error.component:
                    continue
                if severity_order[rule["min_severity"]] > error_level:
                    continue
                matched.update(rule["channels"])
        return list(matched) if matched else ["console"]

    def _alert_console(self, error: EngineSystemError) -> None:
        msg = f"[{error.severity.value}] Union[{error.component}, {error.error_id}] | {error.message}"
        level = getattr(logging, error.severity.value, logging.ERROR)
        self._logger.log(level, msg)

    def _alert_email(self, error: EngineSystemError) -> None:
        cfg = self._email_config
        if cfg is None:
            return
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[{error.severity.value}] {error.component} — {error.message[:80]}"
            msg["From"] = cfg["from_addr"]
            msg["To"] = ", ".join(cfg["to_addrs"])
            body = (
                f"Error ID: {error.error_id}\n"
                f"Timestamp: {error.timestamp.isoformat()}\n"
                f"Component: {error.component}\n"
                f"Severity: {error.severity.value}\n"
                f"Message: {error.message}\n"
                f"Details: {json.dumps(error.details, default=str)}\n"
                f"Stack trace:\n{error.stack_trace}"
            )
            msg.set_content(body)
            with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as s:
                s.starttls()
                s.login(cfg["username"], cfg["password"])
                s.send_message(msg)
        except Exception:
            self._logger.exception("Failed to send email alert")

    def _alert_webhook(self, error: EngineSystemError) -> None:
        cfg = self._webhook_config
        if cfg is None:
            return
        try:
            payload = json.dumps(
                {
                    "error_id": error.error_id,
                    "message": error.message,
                    "component": error.component,
                    "severity": error.severity.value,
                    "timestamp": error.timestamp.isoformat(),
                    "details": error.details,
                    "stack_trace": error.stack_trace,
                    "user_id": error.user_id,
                },
            ).encode("utf-8")
            req = Request(
                cfg["url"],
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    **cfg["headers"],
                },
                method="POST",
            )
            urlopen(req, timeout=10)
        except URLError:
            self._logger.exception("Webhook alert delivery failed")


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


class ErrorHandler:
    """Central error handling service for the platform.

    Responsibilities
        * Create and register :class:`EngineSystemError` instances.
        * Persist errors in an in-memory history (bounded by *max_history*).
        * Forward CRITICAL / ERROR events to the :class:`AlertManager`.
        * Provide query, acknowledge, resolve, and statistics APIs.
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._max_history = max_history
        self._history: deque = deque(maxlen=max_history)
        self._history_map: dict[str, EngineSystemError] = {}
        self._alert_manager: Optional[AlertManager] = None
        self._audit_logger: Optional[logging.Logger] = None
        self._lock = threading.Lock()
        self._logger: logging.Logger = logging.getLogger(__name__)

        try:
            self._audit_logger = logging.getLogger("audit.error")
        except Exception:
            self._logger.debug(
                "Audit logger initialization skipped (logger 'audit.error' unavailable)",
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_alert_manager(self, mgr: AlertManager) -> None:
        """Attach an :class:`AlertManager` for automatic alert dispatch."""
        self._alert_manager = mgr

    def handle_error(
        self,
        component: str,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[dict] = None,
        exception: Optional[BaseException] = None,
        user_id: Optional[str] = None,
    ) -> EngineSystemError:
        """Record and process an error.

        Creates a :class:`EngineSystemError`, logs it to the audit trail, stores
        it in the error history, and triggers alerts for ERROR / CRITICAL
        severity.

        Args:
            component: Source component identifier.
            message: Human-readable error description.
            severity: Severity level (default ERROR).
            details: Optional context dictionary.
            exception: Optional exception whose traceback is captured.
            user_id: Optional associated user identifier.

        Returns:
            The newly created :class:`EngineSystemError`.
        """
        error = EngineSystemError(
            error_id=str(uuid.uuid4()),
            message=message,
            component=component,
            severity=severity,
            timestamp=datetime.now(UTC),
            details=details or {},
            stack_trace="".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__),
            )
            if exception
            else "",
            user_id=user_id,
        )

        self._store(error)
        self._log_audit(error)

        if severity in (ErrorSeverity.CRITICAL, ErrorSeverity.ERROR):
            self._dispatch_alert(error)

        return error

    def get_error_history(
        self,
        component: Optional[str] = None,
        severity: Optional[ErrorSeverity] = None,
        limit: int = 100,
    ) -> list[EngineSystemError]:
        """Query error history with optional filters.

        Args:
            component: Filter by component name.
            severity: Filter by severity level.
            limit: Maximum number of results (newest first).

        Returns:
            Matching errors ordered newest-first.
        """
        with self._lock:
            result = list(self._history)
        if component:
            result = [e for e in result if e.component == component]
        if severity:
            result = [e for e in result if e.severity == severity]
        result.sort(key=lambda e: e.timestamp, reverse=True)
        return result[:limit]

    def get_error_by_id(self, error_id: str) -> Optional[EngineSystemError]:
        """Retrieve a single error by its UUID.

        Args:
            error_id: The error identifier.

        Returns:
            The :class:`EngineSystemError` or *None* if not found.
        """
        with self._lock:
            return self._history_map.get(error_id)

    def acknowledge_error(self, error_id: str, user_id: str) -> bool:
        """Mark an error as acknowledged by a user.

        Args:
            error_id: Error identifier.
            user_id: User acknowledging the error.

        Returns:
            *True* if the error was found and updated.
        """
        error = self.get_error_by_id(error_id)
        if error is None:
            return False
        with self._lock:
            error.acknowledged = True
            error.details["acknowledged_by"] = user_id
            error.details["acknowledged_at"] = datetime.now(UTC).isoformat()
        return True

    def resolve_error(self, error_id: str, resolution: str) -> bool:
        """Mark an error as resolved with a resolution note.

        Args:
            error_id: Error identifier.
            resolution: Description of the resolution.

        Returns:
            *True* if the error was found and updated.
        """
        error = self.get_error_by_id(error_id)
        if error is None:
            return False
        with self._lock:
            error.resolution = resolution
        return True

    def get_error_statistics(self) -> dict:
        """Compute error statistics grouped by component, severity, and time.

        Returns:
            A dictionary with ``by_component``, ``by_severity``, ``last_hour``,
            ``last_24h``, ``total``, and ``unacknowledged`` counts.
        """
        now = datetime.now(UTC)
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)

        with self._lock:
            errors = list(self._history)

        by_component: dict[str, int] = defaultdict(int)
        by_severity: dict[str, int] = defaultdict(int)
        last_hour = 0
        last_24h = 0
        unacknowledged = 0

        for e in errors:
            by_component[e.component] += 1
            by_severity[e.severity.value] += 1
            if e.timestamp >= one_hour_ago:
                last_hour += 1
            if e.timestamp >= one_day_ago:
                last_24h += 1
            if not e.acknowledged:
                unacknowledged += 1

        return {
            "by_component": dict(by_component),
            "by_severity": dict(by_severity),
            "last_hour": last_hour,
            "last_24h": last_24h,
            "total": len(errors),
            "unacknowledged": unacknowledged,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _store(self, error: EngineSystemError) -> None:
        with self._lock:
            if len(self._history) >= self._max_history:
                old = self._history.popleft()
                self._history_map.pop(old.error_id, None)
            self._history.append(error)
            self._history_map[error.error_id] = error

    def _log_audit(self, error: EngineSystemError) -> None:
        logger = self._audit_logger
        if logger is None:
            return
        try:
            level = getattr(logging, error.severity.value, logging.ERROR)
            self._audit_logger.log(
                level,
                "[%s] [%s] Union[%s, error_id=%s]" % (
                    error.severity.value,
                    error.component,
                    error.message,
                    error.error_id,
                ),
            )
        except Exception:
            logging.getLogger(__name__).debug(
                "Audit log write skipped for error %s", error.error_id,
            )

    def _dispatch_alert(self, error: EngineSystemError) -> None:
        mgr = self._alert_manager
        if mgr is None:
            return
        try:
            mgr.trigger_alert(error)
        except Exception:
            # Must not mask the original failure with missing logger attributes.
            self._logger.exception("Alert dispatch failed")


# ---------------------------------------------------------------------------
# Auto-recovery manager
# ---------------------------------------------------------------------------


class AutoRecoveryManager:
    """Attempts automatic recovery from known error patterns.

    Recovery actions are registered per component with an error pattern
    (a substring match against the error message) and a callable.  Each
    action is subject to a cooldown to prevent rapid retry loops.
    """

    def __init__(
        self,
        error_handler: ErrorHandler,
        resilience_module: Any = None,
    ) -> None:
        self._error_handler = error_handler
        self._resilience_module = resilience_module
        self._actions: list[dict] = []
        self._status: dict[str, dict] = {}
        self._lock = threading.Lock()

    def register_recovery_action(
        self,
        component: str,
        error_pattern: str,
        action_fn: Callable[[EngineSystemError], bool],
        cooldown_seconds: int = 300,
        action_name: Optional[str] = None,
    ) -> None:
        """Register an automatic recovery action.

        When an error matching *component* and *error_pattern* occurs,
        *action_fn* will be invoked with the error.  The function should
        return ``True`` on success.

        Args:
            component: Component name to match.
            error_pattern: Substring searched in the error message.
            action_fn: Callable receiving the error, returning bool.
            cooldown_seconds: Minimum seconds between attempts (default 300).
            action_name: Display name (defaults to *error_pattern*).
        """
        name = action_name or error_pattern
        with self._lock:
            self._actions.append(
                {
                    "component": component,
                    "error_pattern": error_pattern,
                    "action_fn": action_fn,
                    "cooldown_seconds": cooldown_seconds,
                    "action_name": name,
                },
            )
            self._status.setdefault(
                name,
                {
                    "action_name": name,
                    "success": True,
                    "attempts": 0,
                    "last_attempt_time": None,
                    "last_success": True,
                },
            )

    def attempt_recovery(self, error: EngineSystemError) -> bool:
        """Attempt automatic recovery for *error*.

        Iterates registered actions and runs the first matching one
        that is not in cooldown.

        Args:
            error: The error to recover from.

        Returns:
            *True* if a recovery action succeeded.
        """
        with self._lock:
            relevant = [
                a
                for a in self._actions
                if a["component"] == error.component and a["error_pattern"] in error.message
            ]

        for action in relevant:
            name = action["action_name"]
            status = self._status[name]

            if self._in_cooldown(status, action["cooldown_seconds"]):
                continue

            status["attempts"] += 1
            status["last_attempt_time"] = time.time()

            try:
                ok = action["action_fn"](error)
                status["last_success"] = ok
                status["success"] = status.get("success", True) and ok
            except Exception:
                status["last_success"] = False
                status["success"] = False
                ok = False

            if ok:
                self._error_handler.resolve_error(
                    error.error_id,
                    f"Auto-recovered by {name}",
                )
                return True
        return False

    def get_recovery_status(self) -> list[dict]:
        """Return status for all registered recovery actions.

        Returns:
            List of dicts with action name, success flag, attempt count,
            and last attempt time.
        """
        with self._lock:
            return [
                {
                    "action_name": s["action_name"],
                    "success": s["success"],
                    "attempts": s["attempts"],
                    "last_attempt_time": s["last_attempt_time"],
                    "last_success": s["last_success"],
                }
                for s in self._status.values()
            ]

    @staticmethod
    def _in_cooldown(status: dict, cooldown: int) -> bool:
        last = status.get("last_attempt_time")
        if last is None:
            return False
        return (time.time() - last) < cooldown


# ---------------------------------------------------------------------------
# Component guard
# ---------------------------------------------------------------------------


@contextmanager
def component_guard(
    component_name: str,
    error_handler: ErrorHandler,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    details: Optional[dict] = None,
    user_id: Optional[str] = None,
):
    """Context manager that catches exceptions and routes them to the handler.

    Usage::

        with component_guard("load_flow", handler) as ctx:
            result = run_solver()

    If the inner block raises, the exception is captured as a
    :class:`EngineSystemError` via :meth:`ErrorHandler.handle_error`.  When the
    guard's severity is ``CRITICAL`` the exception is re-raised after
    handling; otherwise it is swallowed.

    Args:
        component_name: Component identifier for the error.
        error_handler: The :class:`ErrorHandler` instance.
        severity: Severity to assign (default ERROR).
        details: Optional context dict merged with exception info.
        user_id: Optional user identifier.

    Yields:
        The context manager itself (no meaningful value).
    """
    try:
        yield
    except Exception as exc:
        error_handler.handle_error(
            component=component_name,
            message=str(exc),
            severity=severity,
            details=details,
            exception=exc,
            user_id=user_id,
        )
        if severity == ErrorSeverity.CRITICAL:
            raise


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

_handler: Optional[ErrorHandler] = None
_alert_manager: Optional[AlertManager] = None
_auto_recovery: Optional[AutoRecoveryManager] = None
_lock = threading.Lock()


def get_error_handler() -> ErrorHandler:
    """Return the application-wide :class:`ErrorHandler` singleton."""
    global _handler
    if _handler is None:
        with _lock:
            if _handler is None:
                _handler = ErrorHandler()
    return _handler


def get_alert_manager() -> AlertManager:
    """Return the application-wide :class:`AlertManager` singleton."""
    global _alert_manager
    if _alert_manager is None:
        with _lock:
            if _alert_manager is None:
                _alert_manager = AlertManager()
    return _alert_manager


def get_auto_recovery_manager() -> AutoRecoveryManager:
    """Return the application-wide :class:`AutoRecoveryManager` singleton.

    The singleton is lazily created with :func:`get_error_handler` as its
    ``error_handler`` argument.
    """
    global _auto_recovery
    if _auto_recovery is None:
        with _lock:
            if _auto_recovery is None:
                _auto_recovery = AutoRecoveryManager(get_error_handler())
    return _auto_recovery
