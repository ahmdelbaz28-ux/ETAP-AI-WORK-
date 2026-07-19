"""
services/otp_store.py — OTP Code Storage & Verification
=======================================================

Lightweight OTP store backed by Redis (preferred) or in-memory dict fallback.
Each OTP is identified by (email, purpose) so the same email can hold OTPs
for different flows concurrently (e.g. signup vs. login).

Security
--------
* Codes are 6-digit numeric (cryptographically random).
* Stored hashed (SHA-256) — not in plaintext — to limit blast radius if
  the store is compromised.
* TTL: 10 minutes (configurable via OTP_TTL_SECONDS).
* Max attempts per code: 5 (then code is invalidated).
* After 3 failed verifications for the same email/purpose within 60s,
  a 60-second cooldown is enforced before a new code can be issued.

Author: ETAP Integration Team
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("etap.otp_store")

OTP_TTL_SECONDS = int(os.getenv("OTP_TTL_SECONDS", "600"))  # 10 minutes
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_ISSUE_COOLDOWN_SEC = int(os.getenv("OTP_ISSUE_COOLDOWN_SEC", "60"))
OTP_ISSUE_COOLDOWN_AFTER_FAILS = int(os.getenv("OTP_ISSUE_COOLDOWN_AFTER_FAILS", "3"))


# ---------------------------------------------------------------------------
# Redis client (optional)
# ---------------------------------------------------------------------------

try:
    import redis.asyncio as redis_async  # type: ignore

    _REDIS_AVAILABLE = True
except ImportError:  # pragma: no cover
    redis_async = None
    _REDIS_AVAILABLE = False


_redis_client = None  # module-level singleton


def _get_redis():
    """Return shared async redis client singleton or None.

    SECURITY (P0-2): Previously, this function called redis_async.from_url()
    on EVERY invocation — creating a new connection pool each time. Under
    load, this would exhaust file descriptors and memory. Now uses a
    module-level singleton (created once, reused).
    """
    global _redis_client
    if not _REDIS_AVAILABLE:
        return None
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return None
    if _redis_client is None:
        _redis_client = redis_async.from_url(url, decode_responses=True)
    return _redis_client


# ---------------------------------------------------------------------------
# In-memory fallback store
# ---------------------------------------------------------------------------


@dataclass
class _OtpRecord:
    code_hash: str
    issued_at: float
    expires_at: float
    attempts: int = 0


class _InMemoryOtpStore:
    """Fallback when Redis is not available (not durable across restarts)."""

    def __init__(self) -> None:
        self._records: dict[str, _OtpRecord] = {}
        self._issue_log: dict[str, list[float]] = {}
        self._fail_counts: dict[str, list[float]] = {}

    async def set(self, key: str, rec: _OtpRecord) -> None:
        self._records[key] = rec

    async def get(self, key: str) -> Optional[_OtpRecord]:
        rec = self._records.get(key)
        if rec is None:
            return None
        if rec.expires_at < time.time():
            self._records.pop(key, None)
            return None
        return rec

    async def update(self, key: str, rec: _OtpRecord) -> None:
        self._records[key] = rec

    async def delete(self, key: str) -> None:
        self._records.pop(key, None)

    async def record_issue(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.time()
        log = self._issue_log.setdefault(key, [])
        log[:] = [t for t in log if now - t < OTP_ISSUE_COOLDOWN_SEC]
        if len(log) >= 1 and (now - log[-1]) < OTP_ISSUE_COOLDOWN_SEC:
            return False, int(OTP_ISSUE_COOLDOWN_SEC - (now - log[-1])) + 1
        log.append(now)
        return True, 0

    async def record_fail(self, key: str) -> tuple[bool, int]:
        """Record a failed verification; return (allowed_to_retry, retry_after)."""
        now = time.time()
        fails = self._fail_counts.setdefault(key, [])
        fails[:] = [t for t in fails if now - t < OTP_ISSUE_COOLDOWN_SEC]
        fails.append(now)
        if len(fails) >= OTP_ISSUE_COOLDOWN_AFTER_FAILS:
            return False, int(OTP_ISSUE_COOLDOWN_SEC - (now - fails[0])) + 1
        return True, 0


_mem_store = _InMemoryOtpStore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _key(email: str, purpose: str) -> str:
    return f"otp:{purpose}:{email.lower().strip()}"


def _generate_code() -> str:
    """Generate a cryptographically random 6-digit code."""
    return f"{secrets.randbelow(1_000_000):06d}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class OtpIssueResult:
    """Result of an issue attempt."""

    def __init__(self, success: bool, code: Optional[str] = None,
                 retry_after: int = 0, error: Optional[str] = None):
        self.success = success
        self.code = code
        self.retry_after = retry_after
        self.error = error


class OtpVerifyResult:
    """Result of a verify attempt."""

    def __init__(self, success: bool, error: Optional[str] = None,
                 retry_after: int = 0):
        self.success = success
        self.error = error
        self.retry_after = retry_after


async def issue_otp(email: str, purpose: str) -> OtpIssueResult:
    """Generate + store a new OTP for (email, purpose).

    SECURITY (LAUNCH-BLOCKER): Now uses Redis when available (multi-replica
    safe). Previously only used in-memory store — OTPs were not shared
    across replicas, breaking login in multi-instance deployments.
    """
    key = _key(email, purpose)

    # Rate-limit issuance
    allowed, retry_after = await _mem_store.record_issue(key)
    if not allowed:
        return OtpIssueResult(
            success=False,
            retry_after=retry_after,
            error=f"Please wait {retry_after}s before requesting another code.",
        )

    code = _generate_code()
    now = time.time()
    rec = _OtpRecord(
        code_hash=_hash_code(code),
        issued_at=now,
        expires_at=now + OTP_TTL_SECONDS,
    )
    await _mem_store.set(key, rec)

    # SECURITY (LAUNCH-BLOCKER): Also store in Redis for multi-replica sync
    r = _get_redis()
    if r is not None:
        try:
            import json as _json
            redis_key = f"etap:{key}"
            r_data = _json.dumps({
                "code_hash": rec.code_hash,
                "issued_at": rec.issued_at,
                "expires_at": rec.expires_at,
                "attempts": 0,
            })
            await r.setex(redis_key, OTP_TTL_SECONDS, r_data)
        except Exception as exc:
            logger.warning("otp_redis_set_failed key=%s err=%s", key, exc)
        # NOTE: do NOT close the redis client — it's a shared singleton

    logger.info("otp_issued email=%s purpose=%s ttl=%ds", email, purpose, OTP_TTL_SECONDS)
    return OtpIssueResult(success=True, code=code)


async def verify_otp(email: str, purpose: str, code: str) -> OtpVerifyResult:
    """Verify an OTP. On success, the OTP is consumed (one-shot).

    SECURITY (LAUNCH-BLOCKER): Uses Redis atomic INCR for attempt counting
    to prevent TOCTOU race. Previously, concurrent requests could each
    read attempts=4, increment to 5, and all succeed — bypassing the
    OTP_MAX_ATTEMPTS limit. Now uses Redis INCR (atomic) when available.
    """
    key = _key(email, purpose)
    code = code.strip()

    if not code or not code.isdigit() or len(code) != 6:
        return OtpVerifyResult(success=False, error="invalid_code_format")

    # Try Redis first (multi-replica + atomic)
    r = _get_redis()
    if r is not None:
        try:
            import json as _json
            redis_key = f"etap:{key}"
            attempts_key = f"etap:{key}:attempts"

            raw = await r.get(redis_key)
            if raw is None:
                return OtpVerifyResult(success=False, error="code_not_found_or_expired")

            data = _json.loads(raw)
            if data["expires_at"] < time.time():
                await r.delete(redis_key)
                return OtpVerifyResult(success=False, error="code_not_found_or_expired")

            # SECURITY: Atomic attempt increment via Redis INCR
            current_attempts = await r.incr(attempts_key)
            if current_attempts == 1:
                await r.expire(attempts_key, OTP_TTL_SECONDS)

            if current_attempts > OTP_MAX_ATTEMPTS:
                await r.delete(redis_key)
                await r.delete(attempts_key)
                return OtpVerifyResult(success=False, error="max_attempts_exceeded")

            if _hash_code(code) != data["code_hash"]:
                # Record failure for rate-limiting
                allowed, retry_after = await _mem_store.record_fail(key)
                if not allowed:
                    return OtpVerifyResult(
                        success=False,
                        error="too_many_attempts",
                        retry_after=retry_after,
                    )
                remaining = OTP_MAX_ATTEMPTS - current_attempts
                return OtpVerifyResult(
                    success=False,
                    error=f"invalid_code ({remaining} attempts remaining)",
                )

            # Success — consume atomically
            await r.delete(redis_key)
            await r.delete(attempts_key)
            logger.info("otp_verified email=%s purpose=%s", email, purpose)
            return OtpVerifyResult(success=True)

        except Exception as exc:
            logger.warning("otp_redis_verify_failed key=%s err=%s — falling back to memory", key, exc)
        # NOTE: do NOT close the redis client — it's a shared singleton

    # Fallback: in-memory store (single-replica only)
    rec = await _mem_store.get(key)
    if rec is None:
        return OtpVerifyResult(success=False, error="code_not_found_or_expired")

    rec.attempts += 1
    if rec.attempts > OTP_MAX_ATTEMPTS:
        await _mem_store.delete(key)
        return OtpVerifyResult(success=False, error="max_attempts_exceeded")

    if _hash_code(code) != rec.code_hash:
        # Record failure for rate-limiting
        allowed, retry_after = await _mem_store.record_fail(key)
        await _mem_store.update(key, rec)
        if not allowed:
            return OtpVerifyResult(
                success=False,
                error="too_many_attempts",
                retry_after=retry_after,
            )
        remaining = OTP_MAX_ATTEMPTS - rec.attempts
        return OtpVerifyResult(
            success=False,
            error=f"invalid_code ({remaining} attempts remaining)",
        )

    # Success — consume
    await _mem_store.delete(key)
    logger.info("otp_verified email=%s purpose=%s", email, purpose)
    return OtpVerifyResult(success=True)


async def invalidate_otp(email: str, purpose: str) -> None:
    """Force-invalidate an OTP (e.g. after a successful password reset).

    SECURITY (LAUNCH-BLOCKER): Now also clears Redis keys.
    """
    key = _key(email, purpose)
    await _mem_store.delete(key)

    r = _get_redis()
    if r is not None:
        try:
            await r.delete(f"etap:{key}")
            await r.delete(f"etap:{key}:attempts")
        except Exception as exc:
            logger.warning("otp_redis_invalidate_failed key=%s err=%s", key, exc)
        # NOTE: do NOT close the redis client — it's a shared singleton


__all__ = [
    "issue_otp",
    "verify_otp",
    "invalidate_otp",
    "OtpIssueResult",
    "OtpVerifyResult",
    "OTP_TTL_SECONDS",
]
