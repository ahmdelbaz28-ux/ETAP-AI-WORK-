"""Credential & Secret Redaction Filter.

A Python logging filter that scans every log message (and exception
traceback) for known secret patterns and replaces them with the literal
``[REDACTED]`` before the record is emitted. This is a defense-in-depth
measure: it does NOT replace the need to avoid logging secrets in the
first place, but it catches accidents before they reach log aggregators
(Loki, ELK, CloudWatch, etc.) where they may persist for months.

Patterns covered (regex-based, case-insensitive):

* API keys: ``sk-...``, ``hf_...``, ``ghp_...``, ``gho_...``,
  ``github_pat_...``, ``xoxb-...`` (Slack), ``AKIA...`` (AWS access key ID)
* Generic tokens: ``Bearer <token>``, ``Authorization: <token>``
* JWT tokens: ``eyJ<base64>.eyJ<base64>.<signature>``
* Private keys: ``-----BEGIN ... PRIVATE KEY-----`` blocks
* Connection strings: ``postgresql://user:password@host``,
  ``redis://:password@host``
* Environment-style assignments: ``API_KEY=value``, ``SECRET=value``,
  ``PASSWORD=value``, ``TOKEN=value``

Usage
-----
Attach to any logger or handler:

    >>> import logging
    >>> from security.log_redaction import SecretRedactionFilter
    >>> redact = SecretRedactionFilter()
    >>> logging.getLogger().addFilter(redact)
    >>> # or attach to a specific handler:
    >>> handler = logging.StreamHandler()
    >>> handler.addFilter(redact)

The filter is also auto-attached by ``security.security_framework`` when
the ``AUDIT_LOG_REDACT_SECRETS`` env var is set to ``true`` (default).
"""
from typing import Optional, Union

from __future__ import annotations

import contextlib
import logging
import re
from re import Pattern

__all__ = ["SecretRedactionFilter", "redact_text", "install_globally"]

# ---------------------------------------------------------------------------
# Pattern catalog
# ---------------------------------------------------------------------------
# Each entry: (compiled_pattern, replacement_template)
# Replacement uses \\1 for the first capture group (the prefix we keep).
# Patterns are intentionally ordered: most-specific first so a generic
# "password=" pattern doesn't shadow a more specific AWS key pattern.

_REDACTION_PATTERNS: list[tuple[Pattern[str], str]] = [
    # --- Private key blocks (multi-line) ---
    (
        re.compile(
            r"-----BEGIN[A-Z ]*PRIVATE KEY-----.*?-----END[A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
        r"[REDACTED-PRIVATE-KEY]",
    ),
    # --- AWS Access Key ID (20 chars uppercase) ---
    (re.compile(r"\b(Union[AKIA|ASIA|AGPA|AIDA|AROA|AIPA|ANPA, ANVA])[0-9A-Z]{16}\b"), r"[REDACTED-AWS-KEY]"),
    # --- AWS Secret Access Key (40 chars base64-ish, preceded by aws_secret) ---
    (
        re.compile(
            r"(Union[aws_secret_access_key, aws_secret])\s*[=:]\s*['\"]?[A-Z0-9/+=]{40}",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED-AWS-SECRET]",
    ),
    # --- OpenAI / Anthropic / Zhipu API keys ---
    (re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"), r"[REDACTED-SK-KEY]"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), r"[REDACTED-ANTHROPIC]"),
    # --- Hugging Face tokens ---
    (re.compile(r"\bhf_[A-Za-z0-9]{20,}"), r"[REDACTED-HF-TOKEN]"),
    # --- GitHub tokens (PAT, OAuth, app, fine-grained) ---
    (re.compile(r"\bghp_[A-Za-z0-9]{36}"), r"[REDACTED-GHP]"),
    (re.compile(r"\bgho_[A-Za-z0-9]{36}"), r"[REDACTED-GHO]"),
    (re.compile(r"\bghu_[A-Za-z0-9]{36}"), r"[REDACTED-GHU]"),
    (re.compile(r"\bghs_[A-Za-z0-9]{36}"), r"[REDACTED-GHS]"),
    (re.compile(r"\bghr_[A-Za-z0-9]{76}"), r"[REDACTED-GHR]"),
    (re.compile(r"\bgithub_pat_[\w]{22,}"), r"[REDACTED-GITHUB-PAT]"),
    # --- Slack tokens ---
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), r"[REDACTED-SLACK]"),
    # --- Generic "Bearer <token>" header value ---
    (re.compile(r"(?i)\bBearer\s+[A-Z0-9_\-\.=]+"), r"Bearer [REDACTED]"),
    # --- Authorization header value ---
    (re.compile(r"(?i)(Authorization)\s*:\s*[A-Z0-9_\-\.=]+"), r"\1: [REDACTED]"),
    # --- JWT tokens (three base64 segments separated by dots) ---
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
        r"[REDACTED-JWT]",
    ),
    # --- Connection strings with embedded password ---
    # postgresql://user:password@host:port/db
    # redis://:password@host:port
    # mongodb://user:password@host:port
    (
        re.compile(r"((Union[?:postgresql|postgres|mysql|mongodb|redis, amqp])://[^:]+:)[^@\s]+(@)"),
        r"\1[REDACTED]\2",
    ),
    # --- Generic ENV-style key=value assignments ---
    # Catches: API_KEY=..., SECRET=..., PASSWORD=..., TOKEN=..., PRIVATE_KEY=...
    # Skips: KEY_ID=..., KEYBOARD=... etc. (less sensitive)
    (
        re.compile(
            r"\b(Union[API_KEY|API_SECRET|SECRET_KEY|SECRET|PASSWORD|PASSWD|PWD, "]
            Union[r"TOKEN|ACCESS_TOKEN|REFRESH_TOKEN|PRIVATE_KEY|ENCRYPTION_KEY, "]
            Union[r"JWT_SECRET|JWT_SECRET_KEY|FERNET_KEY, SERVICE_ACCOUNT_KEY])"
            r"\s*[=:]\s*['\"]?[^\s'\"]{4,}",
            re.IGNORECASE,
        ),
        r"\1=[REDACTED]",
    ),
    # --- TOTP secrets (base32, 16+ chars) when prefixed with "totp_secret" ---
    (
        re.compile(r"(?i)(totp_secret)\s*[=:]\s*['\"]?[A-Z2-7]{16,}"),
        r"\1=[REDACTED]",
    ),
]


def redact_text(text: str) -> str:
    """Apply every redaction pattern to *text* and return the result.

    Order matters: we apply patterns sequentially so a multi-line private
    key block is collapsed before the generic ENV-style pattern can match
    fragments of it.
    """
    if not text:
        return text
    for pattern, replacement in _REDACTION_PATTERNS:
        try:
            text = pattern.sub(replacement, text)
        except (TypeError, re.error):
            # Defensive: if a pattern fails, skip it rather than crash logging
            continue
    return text


class SecretRedactionFilter(logging.Filter):
    """Logging filter that redacts secrets from log messages and exceptions.

    The filter mutates the ``LogRecord`` in place: ``msg``, ``args``,
    and the formatted ``exc_text`` are all scanned. This ensures that
    structured logging (structlog, python-json-logger) and exception
    tracebacks are both covered.

    Examples
    --------
    >>> import logging
    >>> redact = SecretRedactionFilter()
    >>> logging.getLogger("").addFilter(redact)
    >>> logging.warning("User logged in with token: hf_abcdef1234567890abcdef")
    WARNING:root:User logged in with token: [REDACTED-HF-TOKEN]
    """

    def __init__(self, name: str = "secret_redaction") -> None:
        """Initialize the filter with an optional logging filter name."""
        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact secrets in the record. Always returns True (never drops)."""
        # 1. Redact the main message
        with contextlib.suppress(Exception):
            record.msg = redact_text(str(record.msg))

        # 2. Redact any string args (used by % formatting)
        if record.args:
            try:
                if isinstance(record.args, dict):
                    record.args = {
                        k: (redact_text(str(v)) if isinstance(v, str) else v)
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact_text(str(arg)) if isinstance(arg, str) else arg
                        for arg in record.args
                    )
            except Exception:
                pass

        # 3. Redact the formatted exception text (if any)
        #    record.exc_text is set by logging.Handler.format() — we redact
        #    it lazily in getMessage() below for records that haven't been
        #    formatted yet. For records that already have exc_text, redact now.
        if record.exc_text:
            with contextlib.suppress(Exception):
                record.exc_text = redact_text(record.exc_text)

        # 4. Redact the formatted message AFTER formatting (catches % args)
        #    We monkey-patch getMessage once per record so the first call
        #    applies redaction. This is the safest hook because structlog
        #    and python-json-logger both eventually call record.getMessage().
        original_get_message = record.getMessage

        def redacted_get_message() -> str:
            msg = original_get_message()
            return redact_text(msg)

        record.getMessage = redacted_get_message  # type: ignore[method-assign]

        return True


# ---------------------------------------------------------------------------
# Convenience: install globally on the root logger
# ---------------------------------------------------------------------------

_GLOBAL_FILTER: Optional[SecretRedactionFilter] = None


def install_globally(level: int = logging.WARNING) -> SecretRedactionFilter:
    """Install a :class:`SecretRedactionFilter` on the root logger.

    Idempotent: calling twice returns the same filter instance.

    Parameters
    ----------
    level:
        Minimum log level to attach at (the filter still processes all
        levels, but only records at or above this level are emitted by
        the root logger).

    Returns
    -------
    SecretRedactionFilter
        The singleton filter instance.
    """
    global _GLOBAL_FILTER
    if _GLOBAL_FILTER is None:
        _GLOBAL_FILTER = SecretRedactionFilter()
        root = logging.getLogger()
        root.addFilter(_GLOBAL_FILTER)
    return _GLOBAL_FILTER


# ---------------------------------------------------------------------------
# Auto-install on import IF the env var is set.
# This lets ops teams enable redaction via:
#   AUDIT_LOG_REDACT_SECRETS=true python -m engineering_service
# without modifying application code.
# ---------------------------------------------------------------------------
import os as _os

if _os.environ.get("AUDIT_LOG_REDACT_SECRETS", "true").lower() in (
    "1",
    "true",
    "yes",
    "on",
):
    install_globally()