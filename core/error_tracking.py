"""
core/error_tracking.py — Sentry-ready error tracking hooks for AhmedETAP.

Provides a unified interface for error reporting that works with or without
Sentry installed. When Sentry is configured (SENTRY_DSN env var set), errors
are sent to Sentry. When not configured, errors fall back to structured
logging via structlog.

Usage:
    from core.error_tracking import capture_exception, set_user_context, add_breadcrumb

    try:
        risky_operation()
    except Exception as exc:
        capture_exception(exc, context={"study_id": "abc-123"})

Configuration:
    SENTRY_DSN           — Sentry DSN URL (https://xxx@sentry.io/xxx)
    SENTRY_ENVIRONMENT   — environment name (production, staging, development)
    SENTRY_RELEASE       — release version (auto-detected from VERSION file)
    SENTRY_TRACES_SAMPLE_RATE — float 0.0-1.0 for performance monitoring
    SENTRY_PROFILES_SAMPLE_RATE — float 0.0-1.0 for profiling

Security:
    - Sensitive data (API keys, passwords, JWT tokens) is automatically
      scrubbed from error context before sending to Sentry.
    - User IP addresses are never sent.
    - Request bodies larger than 8KB are truncated.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── Sensitive data scrubbing ────────────────────────────────────────────────
# Patterns that match common secret formats. Any value matching these patterns
# is replaced with '[REDACTED]' before being sent to Sentry or logged.
_SENSITIVE_PATTERNS = [
    # API keys
    re.compile(r'sk-[a-zA-Z0-9]{20,}', re.IGNORECASE),
    re.compile(r'ghp_[a-zA-Z0-9]{36}', re.IGNORECASE),
    re.compile(r'github_pat_[a-zA-Z0-9_]{20,}', re.IGNORECASE),
    re.compile(r'hf_[a-zA-Z0-9]{30,}', re.IGNORECASE),
    re.compile(r'sb_secret_[a-zA-Z0-9_-]+', re.IGNORECASE),
    re.compile(r'sb_publishable_[a-zA-Z0-9_-]+', re.IGNORECASE),
    # JWT tokens (eyJ... header.payload.signature)
    re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'),
    # Bearer tokens
    re.compile(r'Bearer\s+[a-zA-Z0-9_.-]{20,}', re.IGNORECASE),
    # Generic API key patterns in JSON
    re.compile(r'["\'](?:api[_-]?key|apikey|secret|password|token|jwt)["\']\s*:\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
]

# Keys whose VALUES should be redacted entirely
_SENSITIVE_KEYS = {
    'password', 'passwd', 'pwd',
    'api_key', 'apikey', 'api-key',
    'secret', 'secret_key', 'secretkey',
    'token', 'access_token', 'refresh_token', 'auth_token',
    'jwt', 'jwt_secret', 'jwt_secret_key',
    'authorization',
    'cookie',
    'session_id', 'sessionid',
    'private_key', 'privatekey',
    'fernet_key', 'encryption_key',
    'service_role_key',
    'supabase_service_role_key',
    'supabase_anon_key',
    'neo4j_password',
    'redis_password',
    'postgres_password',
    'openai_api_key', 'anthropic_api_key', 'google_api_key',
    'nvidia_api_key', 'huggingface_token', 'hf_token',
    'langfuse_secret_key', 'langfuse_public_key',
    'langwatch_api_key', 'smithery_api_key',
    'vercel_token', 'github_token', 'gh_pat',
    'cloudflare_api_token',
}

_MAX_CONTEXT_VALUE_LENGTH = 1024  # Truncate long values
_MAX_BREADCRUMB_SIZE = 4096


def _scrub_value(value: Any) -> Any:
    """Recursively scrub sensitive data from a value."""
    if isinstance(value, str):
        # Apply regex patterns to redact secrets
        scrubbed = value
        for pattern in _SENSITIVE_PATTERNS:
            scrubbed = pattern.sub('[REDACTED]', scrubbed)
        # Truncate very long strings
        if len(scrubbed) > _MAX_CONTEXT_VALUE_LENGTH:
            scrubbed = scrubbed[:_MAX_CONTEXT_VALUE_LENGTH] + '...[truncated]'
        return scrubbed

    if isinstance(value, dict):
        return {
            k: '[REDACTED]' if k.lower() in _SENSITIVE_KEYS else _scrub_value(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [_scrub_value(item) for item in value]

    return value


def _scrub_context(context: Dict[str, Any]) -> Dict[str, Any]:
    """Scrub sensitive data from a context dict."""
    return {k: _scrub_value(v) for k, v in context.items()}


# ─── Sentry initialization (lazy) ───────────────────────────────────────────

_sentry_initialized = False
_sentry_available = False


def _init_sentry() -> bool:
    """Initialize Sentry SDK if SENTRY_DSN is set. Returns True if active."""
    global _sentry_initialized, _sentry_available

    if _sentry_initialized:
        return _sentry_available

    _sentry_initialized = True

    dsn = os.environ.get('SENTRY_DSN', '').strip()
    if not dsn:
        logger.debug('SENTRY_DSN not set — error tracking falls back to logging')
        return False

    try:
        import sentry_sdk  # type: ignore
        from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore
    except ImportError:
        logger.warning('SENTRY_DSN is set but sentry-sdk is not installed. '
                       'Install with: pip install sentry-sdk')
        return False

    # Read release version from VERSION file
    release = os.environ.get('SENTRY_RELEASE', '')
    if not release:
        version_file = Path(__file__).parent.parent / 'VERSION'
        if version_file.exists():
            release = version_file.read_text().strip()
            release = f'ahmedetap@{release}'

    # Configure Sentry
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'development'),
        release=release or None,
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
        profiles_sample_rate=float(os.environ.get('SENTRY_PROFILES_SAMPLE_RATE', '0.0')),
        # Send default PII: False — we NEVER send IP addresses or cookies
        send_default_pii=False,
        # Don't send request bodies automatically (we scrub them manually)
        max_request_body_size='small',
        integrations=[
            LoggingIntegration(
                level=logging.INFO,        # Capture INFO+ as breadcrumbs
                event_level=logging.ERROR,  # Send ERROR+ as events
            ),
        ],
        # Don't capture HTTP request bodies (may contain user data)
        before_send=_before_send_filter,
        # Sample rate for transactions (performance monitoring)
        sample_rate=1.0,
    )

    _sentry_available = True
    logger.info('Sentry initialized (env=%s, release=%s)',
                os.environ.get('SENTRY_ENVIRONMENT', 'development'),
                release or 'unknown')
    return True


def _before_send_filter(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter sensitive data before sending to Sentry."""
    # Scrub request data
    if 'request' in event:
        event['request'] = _scrub_value(event['request'])

    # Scrub extra context
    if 'extra' in event:
        event['extra'] = _scrub_context(event['extra'])

    # Scrub breadcrumbs
    if 'breadcrumbs' in event:
        for breadcrumb in event['breadcrumbs'].get('values', []):
            if 'data' in breadcrumb:
                breadcrumb['data'] = _scrub_context(breadcrumb['data'])

    # Don't send user IP
    if 'user' in event and 'ip_address' in event['user']:
        event['user']['ip_address'] = None

    return event


# ─── Public API ──────────────────────────────────────────────────────────────

def capture_exception(
    exc: BaseException,
    context: Optional[Dict[str, Any]] = None,
    level: str = 'error',
) -> None:
    """Capture an exception and send to Sentry (if configured) + log it.

    Parameters
    ----------
    exc : BaseException
        The exception to capture.
    context : dict, optional
        Additional context (study_id, user_id, agent_name, etc.).
        Sensitive data is automatically scrubbed.
    level : str
        Logging level: 'error' (default), 'warning', 'info'.
    """
    scrubbed_context = _scrub_context(context or {})

    # Always log (even without Sentry)
    log_method = getattr(logger, level, logger.error)
    log_method('Exception captured: %s: %s', type(exc).__name__, exc, extra=scrubbed_context)

    # Send to Sentry if available
    if _init_sentry():
        try:
            import sentry_sdk  # type: ignore
            with sentry_sdk.push_scope() as scope:
                for key, value in scrubbed_context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_exception(exc)
        except Exception as sentry_err:
            # Never let Sentry itself cause a failure
            logger.debug('Sentry capture failed: %s', sentry_err)


def capture_message(
    message: str,
    level: str = 'info',
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Capture a message (non-exception) and send to Sentry if configured.

    Parameters
    ----------
    message : str
        The message to capture.
    level : str
        Severity: 'info' (default), 'warning', 'error'.
    context : dict, optional
        Additional context. Sensitive data is scrubbed.
    """
    scrubbed_context = _scrub_context(context or {})

    log_method = getattr(logger, level, logger.info)
    log_method(message, extra=scrubbed_context)

    if _init_sentry():
        try:
            import sentry_sdk  # type: ignore
            with sentry_sdk.push_scope() as scope:
                for key, value in scrubbed_context.items():
                    scope.set_extra(key, value)
                sentry_sdk.capture_message(message, level=level)
        except Exception as sentry_err:
            logger.debug('Sentry message capture failed: %s', sentry_err)


def set_user_context(
    user_id: str,
    username: Optional[str] = None,
    email: Optional[str] = None,
    role: Optional[str] = None,
) -> None:
    """Set user context for error tracking.

    SECURITY: IP address is NEVER set. Email is only set if explicitly provided.
    """
    if _init_sentry():
        try:
            import sentry_sdk  # type: ignore
            sentry_sdk.set_user({
                'id': user_id,
                'username': username,
                'email': email,
                'role': role,
                # ip_address intentionally omitted — never send IPs to Sentry
            })
        except Exception as sentry_err:
            logger.debug('Sentry set_user failed: %s', sentry_err)


def add_breadcrumb(
    message: str,
    category: str = 'custom',
    level: str = 'info',
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Add a breadcrumb for debugging error context.

    Breadcrumbs are a trail of events that happened before an error.
    They appear in Sentry's error detail view.
    """
    scrubbed_data = _scrub_context(data or {}) if data else {}

    # Truncate breadcrumb data to prevent oversized payloads
    total_size = sum(len(str(v)) for v in scrubbed_data.values())
    if total_size > _MAX_BREADCRUMB_SIZE:
        scrubbed_data = {'_truncated': True, 'original_size': total_size}

    if _init_sentry():
        try:
            import sentry_sdk  # type: ignore
            sentry_sdk.add_breadcrumb(
                message=message,
                category=category,
                level=level,
                data=scrubbed_data,
            )
        except Exception as sentry_err:
            logger.debug('Sentry add_breadcrumb failed: %s', sentry_err)


def flush() -> None:
    """Flush pending events to Sentry (useful before process exit)."""
    if _sentry_available:
        try:
            import sentry_sdk  # type: ignore
            sentry_sdk.flush(timeout=5.0)
        except Exception:
            pass


# ─── FastAPI middleware integration ──────────────────────────────────────────

def setup_fastapi_error_tracking(app: Any) -> None:
    """Set up error tracking middleware for a FastAPI app.

    Usage:
        from core.error_tracking import setup_fastapi_error_tracking
        setup_fastapi_error_tracking(app)
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse
    import time

    @app.middleware('http')
    async def error_tracking_middleware(request: Request, call_next):
        """Capture unhandled exceptions and add request context breadcrumbs."""
        start_time = time.time()

        # Add breadcrumb for request start
        add_breadcrumb(
            f'{request.method} {request.url.path}',
            category='request',
            level='info',
            data={
                'method': request.method,
                'path': request.url.path,
                'query_params': dict(request.query_params),
                # Don't include headers — may contain API keys
            },
        )

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Add breadcrumb for response
            add_breadcrumb(
                f'Response {response.status_code} ({duration_ms:.0f}ms)',
                category='response',
                level='info' if response.status_code < 400 else 'warning',
                data={
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2),
                },
            )

            return response

        except Exception as exc:
            duration_ms = (time.time() - start_time) * 1000
            capture_exception(
                exc,
                context={
                    'request_method': request.method,
                    'request_path': request.url.path,
                    'duration_ms': round(duration_ms, 2),
                    'request_id': request.headers.get('x-request-id', ''),
                },
                level='error',
            )
            return JSONResponse(
                status_code=500,
                content={'detail': 'Internal server error', 'trace_id': request.headers.get('x-request-id', '')},
            )
