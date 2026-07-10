"""
integrations/resend_email.py — Resend Email Client for AhmedETAP
===============================================================

Async wrapper around the Resend HTTP API for transactional email delivery.

Features
--------
* Pure-stdlib HTTP client (no extra dependency — uses stdlib httpx-async
  if available, falls back to urllib for HF Space cpu-basic).
* Template rendering via ``templates/emails/*.html`` (Jinja2-style placeholders).
* Per-recipient rate-limit guard (prevents resend-storms).
* Structured logging + structured error handling.
* Domain auto-detection: uses ``RESEND_FROM_EMAIL`` if a custom domain is
  verified, otherwise falls back to ``onboarding@resend.dev`` (Resend's
  shared testing sender — useful for HF Space without verified domain).

Endpoints used
--------------
* POST https://api.resend.com/emails  — send email
  (the API key is restricted to this endpoint — that's fine)

Environment variables
---------------------
RESEND_API_KEY          — Required. Your Resend API key (re_...)
RESEND_FROM_EMAIL       — Optional. Verified sender (default: onboarding@resend.dev)
RESEND_FROM_NAME        — Optional. Sender display name (default: "AhmedETAP")
RESEND_REPLY_TO         — Optional. Reply-to address
RESEND_TIMEOUT_SECONDS  — Optional. HTTP timeout (default: 15)
RESEND_MAX_RETRIES      — Optional. Retry count on 5xx (default: 3)
RESEND_ENABLED          — Optional. Master switch (default: true if API key set)

Usage
-----
    from integrations.resend_email import resend_client, EmailParams

    await resend_client.send(EmailParams(
        to="user@example.com",
        subject="Your verification code",
        html="<h1>Code: 123456</h1>",
    ))

Author: ETAP Integration Team
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from email.utils import formataddr
from typing import Any, Optional

logger = logging.getLogger("etap.resend")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RESEND_API_URL = "https://api.resend.com/emails"

# Resend's shared testing sender — works without domain verification
# but is rate-limited (≈ 100 emails/day to any single recipient).
DEFAULT_FROM_EMAIL = "onboarding@resend.dev"
DEFAULT_FROM_NAME = "AhmedETAP"

# Per-recipient rate limit (avoid accidental storms during incidents).
# Default: max 10 emails / 60 seconds per recipient.
RATE_LIMIT_MAX_EMAILS = int(os.getenv("RESEND_RATE_LIMIT_MAX", "10"))
RATE_LIMIT_WINDOW_SEC = int(os.getenv("RESEND_RATE_LIMIT_WINDOW", "60"))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EmailParams:
    """Parameters for a single email send."""

    to: str | list[str]
    subject: str
    html: Optional[str] = None
    text: Optional[str] = None
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    cc: Optional[list[str]] = None
    bcc: Optional[list[str]] = None
    headers: dict[str, str] = field(default_factory=dict)
    tags: list[dict[str, str]] = field(default_factory=list)
    # Internal: set by client
    _attempt: int = 0


@dataclass
class EmailResult:
    """Result of an email send attempt."""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    raw_response: Optional[dict[str, Any]] = None
    elapsed_ms: int = 0


class ResendError(Exception):
    """Raised when Resend API returns a non-retryable error."""

    def __init__(self, message: str, status_code: int = 0, raw: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.raw = raw


# ---------------------------------------------------------------------------
# HTTP client (stdlib-first, optional httpx)
# ---------------------------------------------------------------------------

try:
    import httpx  # type: ignore

    _HAS_HTTPX = True
except ImportError:  # pragma: no cover
    _HAS_HTTPX = False


async def _http_post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    """POST JSON and return (status_code, json_body)."""
    if _HAS_HTTPX:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            try:
                body = resp.json()
            except Exception:
                body = {"_raw": resp.text}
            return resp.status_code, body
    # Fallback: use urllib in a thread (asyncio.to_thread)
    import urllib.error
    import urllib.request

    def _sync_post() -> tuple[int, dict[str, Any]]:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode("utf-8"))
                return r.status, body
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"_raw": str(e)}
            return e.code, body

    return await asyncio.to_thread(_sync_post)


# ---------------------------------------------------------------------------
# Rate-limit guard (per recipient, in-memory)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple sliding-window rate limiter per recipient."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    def check(self, recipient: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        window = RATE_LIMIT_WINDOW_SEC
        max_n = RATE_LIMIT_MAX_EMAILS
        hits = self._hits.setdefault(recipient, [])
        # purge old hits
        hits[:] = [t for t in hits if now - t < window]
        if len(hits) >= max_n:
            retry_after = int(window - (now - hits[0])) + 1
            return False, max(retry_after, 1)
        hits.append(now)
        return True, 0


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------


class ResendEmailClient:
    """Async Resend email client."""

    def __init__(self) -> None:
        self._api_key: Optional[str] = None
        self._from_email: str = DEFAULT_FROM_EMAIL
        self._from_name: str = DEFAULT_FROM_NAME
        self._reply_to: Optional[str] = None
        self._timeout: float = 15.0
        self._max_retries: int = 3
        self._enabled: Optional[bool] = None
        self._rate_limiter = _RateLimiter()

    # -- Configuration ---------------------------------------------------

    def configure(
        self,
        api_key: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """Explicit configuration (overrides env vars)."""
        if api_key is not None:
            self._api_key = api_key
        if from_email is not None:
            self._from_email = from_email
        if from_name is not None:
            self._from_name = from_name
        if reply_to is not None:
            self._reply_to = reply_to
        if timeout is not None:
            self._timeout = timeout
        if max_retries is not None:
            self._max_retries = max_retries
        if enabled is not None:
            self._enabled = enabled

    def _load_from_env(self) -> None:
        """Load configuration from environment variables on first use."""
        self._api_key = self._api_key or os.getenv("RESEND_API_KEY", "").strip() or None
        self._from_email = os.getenv("RESEND_FROM_EMAIL", self._from_email).strip() or self._from_email
        self._from_name = os.getenv("RESEND_FROM_NAME", self._from_name).strip() or self._from_name
        self._reply_to = os.getenv("RESEND_REPLY_TO", "").strip() or None
        self._timeout = float(os.getenv("RESEND_TIMEOUT_SECONDS", str(self._timeout)))
        self._max_retries = int(os.getenv("RESEND_MAX_RETRIES", str(self._max_retries)))
        env_enabled = os.getenv("RESEND_ENABLED", "").strip().lower()
        if env_enabled:
            self._enabled = env_enabled in ("1", "true", "yes", "on")

    @property
    def is_enabled(self) -> bool:
        """True if Resend should be used."""
        if self._enabled is None:
            self._load_from_env()
        # Explicit disabled → False
        if self._enabled is False:
            return False
        # Otherwise enabled iff API key is present
        return bool(self._api_key)

    @property
    def from_address(self) -> str:
        """Return the formatted From header value."""
        return formataddr((self._from_name, self._from_email))

    # -- Send ------------------------------------------------------------

    async def send(self, params: EmailParams) -> EmailResult:
        """Send an email via Resend.

        Returns EmailResult. Never raises (errors are returned in result).
        """
        if not self.is_enabled:
            return EmailResult(
                success=False,
                error="resend_disabled",
                status_code=0,
            )

        # Normalize recipients to list[str]
        recipients = params.to if isinstance(params.to, list) else [params.to]
        if not recipients:
            return EmailResult(success=False, error="no_recipients")

        # Rate-limit per first recipient (the primary addressee)
        allowed, retry_after = self._rate_limiter.check(recipients[0].lower())
        if not allowed:
            logger.warning(
                "resend_rate_limited recipient=%s retry_after=%ds",
                recipients[0],
                retry_after,
            )
            return EmailResult(
                success=False,
                error=f"rate_limited (retry after {retry_after}s)",
            )

        from_addr = formataddr(
            (params.from_name or self._from_name, params.from_email or self._from_email)
        )
        reply_to = params.reply_to or self._reply_to

        payload: dict[str, Any] = {
            "from": from_addr,
            "to": recipients,
            "subject": params.subject,
        }
        if params.html:
            payload["html"] = params.html
        if params.text:
            payload["text"] = params.text
        if reply_to:
            payload["reply_to"] = reply_to
        if params.cc:
            payload["cc"] = params.cc
        if params.bcc:
            payload["bcc"] = params.bcc
        if params.headers:
            payload["headers"] = params.headers
        if params.tags:
            payload["tags"] = params.tags

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        start = time.monotonic()
        last_error: Optional[str] = None
        last_status: Optional[int] = None
        last_body: Optional[dict[str, Any]] = None

        for attempt in range(1, self._max_retries + 1):
            params._attempt = attempt
            try:
                status, body = await _http_post_json(
                    RESEND_API_URL, headers, payload, self._timeout
                )
                last_status = status
                last_body = body

                if status == 200 and isinstance(body, dict) and "id" in body:
                    elapsed = int((time.monotonic() - start) * 1000)
                    logger.info(
                        "resend_send_ok id=%s recipient=%s subject=%r attempt=%d ms=%d",
                        body.get("id"),
                        recipients[0],
                        params.subject[:80],
                        attempt,
                        elapsed,
                    )
                    result = EmailResult(
                        success=True,
                        message_id=body.get("id"),
                        status_code=status,
                        raw_response=body,
                        elapsed_ms=elapsed,
                    )
                    # Auto-log to email send log (best-effort, never fails the send)
                    try:
                        import asyncio

                        from services.email_send_log import log_email_send
                        flow = "unknown"
                        if params.tags:
                            for tag in params.tags:
                                if isinstance(tag, dict) and tag.get("name") == "flow":
                                    flow = tag.get("value", "unknown")
                                    break
                        # Save task reference to prevent premature GC (SonarCloud python:S4142)
                        _log_task = asyncio.create_task(log_email_send(
                            recipient=recipients[0],
                            subject=params.subject,
                            flow=flow,
                            success=True,
                            message_id=result.message_id,
                            status_code=status,
                            elapsed_ms=elapsed,
                            tags=params.tags,
                        ))
                        # Add done callback to clean up and log errors
                        _log_task.add_done_callback(
                            lambda t: t.exception() if not t.cancelled() and t.exception() else None
                        )
                    except Exception:
                        pass  # logging is best-effort
                    return result

                # 4xx — non-retryable (auth, validation, restricted-key)
                if 400 <= status < 500:
                    msg = (
                        body.get("message")
                        if isinstance(body, dict)
                        else str(body)
                    ) or f"HTTP {status}"
                    logger.error(
                        "resend_send_4xx status=%s recipient=%s msg=%s",
                        status, recipients[0], msg,
                    )
                    elapsed_fail = int((time.monotonic() - start) * 1000)
                    fail_result = EmailResult(
                        success=False,
                        error=msg,
                        status_code=status,
                        raw_response=body if isinstance(body, dict) else {"_raw": str(body)},
                        elapsed_ms=elapsed_fail,
                    )
                    # Auto-log failure
                    try:
                        import asyncio

                        from services.email_send_log import log_email_send
                        flow = "unknown"
                        if params.tags:
                            for tag in params.tags:
                                if isinstance(tag, dict) and tag.get("name") == "flow":
                                    flow = tag.get("value", "unknown")
                                    break
                        # Save task reference to prevent premature GC (SonarCloud python:S4142)
                        _log_task = asyncio.create_task(log_email_send(
                            recipient=recipients[0],
                            subject=params.subject,
                            flow=flow,
                            success=False,
                            error=msg,
                            status_code=status,
                            elapsed_ms=elapsed_fail,
                            tags=params.tags,
                        ))
                        _log_task.add_done_callback(
                            lambda t: t.exception() if not t.cancelled() and t.exception() else None
                        )
                    except Exception:
                        pass
                    return fail_result

                # 5xx — retry
                last_error = (
                    body.get("message") if isinstance(body, dict) else str(body)
                ) or f"HTTP {status}"
                logger.warning(
                    "resend_send_5xx status=%s attempt=%d/%d msg=%s",
                    status, attempt, self._max_retries, last_error,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                last_status = 0
                logger.warning(
                    "resend_send_exception attempt=%d/%d err=%s",
                    attempt, self._max_retries, last_error,
                )

            # Exponential backoff
            if attempt < self._max_retries:
                await asyncio.sleep(min(2 ** (attempt - 1), 8))

        return EmailResult(
            success=False,
            error=last_error or "unknown_error",
            status_code=last_status or 0,
            raw_response=last_body,
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

resend_client = ResendEmailClient()


async def send_email(params: EmailParams) -> EmailResult:
    """Convenience function — equivalent to ``resend_client.send(params)``."""
    return await resend_client.send(params)


__all__ = [
    "EmailParams",
    "EmailResult",
    "ResendError",
    "ResendEmailClient",
    "resend_client",
    "send_email",
]
