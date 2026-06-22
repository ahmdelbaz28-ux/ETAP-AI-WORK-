"""
SIEM Integration for AhmedETAP Platform
======================================
Forwards security events to external SIEM systems such as Grafana Loki
and the ELK Stack (Elasticsearch / Logstash / Kibana).

Features:
- Async HTTP forwarding with retry and back-off
- Structured JSON event payloads compatible with common SIEM formats
- Local buffer with overflow protection when the SIEM is temporarily
  unreachable
- Convenience methods for authentication, access-control, and anomaly events
- Graceful handling when ``httpx`` or ``aiohttp`` is not installed (falls
  back to stdlib :func:`urllib.request` in a thread)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Deque, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional async HTTP libraries
# ---------------------------------------------------------------------------

try:
    import httpx

    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

try:
    import aiohttp

    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False

# If neither async HTTP library is available we fall back to urllib
_HAS_ASYNC_HTTP = _HAS_HTTPX or _HAS_AIOHTTP


# ---------------------------------------------------------------------------
# Event schema
# ---------------------------------------------------------------------------


@dataclass
class SecurityEvent:
    """A structured security event payload.

    Parameters
    ----------
    event_id : str
        Unique event identifier (UUID4).
    timestamp : str
        ISO-8601 UTC timestamp.
    event_type : str
        Category of the event (e.g. ``"auth"``, ``"access"``, ``"anomaly"``).
    severity : str
        ``"info"``, ``"warning"``, ``"critical"``.
    source : str
        Originating service/module.
    details : dict
        Arbitrary key-value details about the event.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = ""
    severity: str = "info"
    source: str = "etap-ai-platform"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict suitable for JSON encoding."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "severity": self.severity,
            "source": self.source,
            "details": self.details,
        }

    def to_json(self) -> str:
        """Serialise to a JSON string."""
        return json.dumps(self.to_dict(), default=str)


# ---------------------------------------------------------------------------
# SIEM Forwarder
# ---------------------------------------------------------------------------


class SIEMForwarder:
    """Forward security events to Grafana Loki or ELK Stack.

    Parameters
    ----------
    endpoint : str
        SIEM ingestion endpoint URL.
        - **Loki**: ``http://loki:3100/loki/api/v1/push``
        - **Elasticsearch**: ``http://elasticsearch:9200/etap-security-*/_doc``
    api_key : str
        Optional API key / Bearer token for authentication.
    siem_type : str
        ``"loki"`` or ``"elk"`` (default ``"loki"``).
    labels : dict
        Additional static labels/tags attached to every event.
    buffer_size : int
        Maximum number of events to buffer when the SIEM is unreachable
        (default 10 000).
    retry_attempts : int
        Number of retry attempts per event (default 3).
    retry_delay_seconds : float
        Base delay between retries (doubles each attempt).
    batch_size : int
        Maximum number of events to send in a single request (default 100).
    flush_interval_seconds : float
        Seconds between automatic buffer flushes (default 5.0).
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str = "",
        siem_type: str = "loki",
        labels: Dict[str, str] | None = None,
        buffer_size: int = 10_000,
        retry_attempts: int = 3,
        retry_delay_seconds: float = 1.0,
        batch_size: int = 100,
        flush_interval_seconds: float = 5.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.siem_type = siem_type.lower()
        self.labels = labels or {}
        self.buffer_size = buffer_size
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds

        self._buffer: Deque[SecurityEvent] = deque(maxlen=buffer_size)
        self._lock = threading.Lock()
        self._stats = {
            "forwarded": 0,
            "failed": 0,
            "buffered": 0,
            "total_buffered": 0,  # monotonic counter — never decremented
            "dropped": 0,
        }

        # Validate siem_type
        if self.siem_type not in ("loki", "elk"):
            logger.warning("Unknown SIEM type '%s'; defaulting to 'loki'", self.siem_type)
            self.siem_type = "loki"

    # -- public API ----------------------------------------------------------

    async def forward_event(self, event_type: str, details: dict) -> bool:
        """Forward a security event to the SIEM.

        Parameters
        ----------
        event_type : str
            Event category (e.g. ``"auth"``, ``"access"``, ``"anomaly"``).
        details : dict
            Arbitrary details about the event.

        Returns
        -------
        bool
            ``True`` if the event was sent (or buffered) successfully.
        """
        event = SecurityEvent(
            event_type=event_type,
            severity=details.get("severity", "info"),
            details=details,
        )

        with self._lock:
            if len(self._buffer) >= self.buffer_size:
                # Drop oldest event
                self._buffer.popleft()
                self._stats["dropped"] += 1
                logger.warning("SIEM buffer overflow — oldest event dropped")
            self._buffer.append(event)
            self._stats["buffered"] += 1
            self._stats["total_buffered"] += 1

        # Attempt immediate flush
        return await self.flush()

    async def forward_auth_event(
        self,
        user: str,
        action: str,
        success: bool,
        ip: str,
        extra: dict | None = None,
    ) -> bool:
        """Forward an authentication event.

        Parameters
        ----------
        user : str
            User identifier.
        action : str
            Auth action (e.g. ``"login"``, ``"logout"``, ``"mfa_verify"``).
        success : bool
            Whether the action succeeded.
        ip : str
            Client IP address.
        extra : dict, optional
            Additional details.

        Returns
        -------
        bool
        """
        details: Dict[str, Any] = {
            "category": "auth",
            "user": user,
            "action": action,
            "success": success,
            "ip": ip,
            "severity": "info" if success else "warning",
        }
        if extra:
            details.update(extra)
        return await self.forward_event("auth", details)

    async def forward_access_event(
        self,
        user: str,
        resource: str,
        action: str,
        allowed: bool,
        extra: dict | None = None,
    ) -> bool:
        """Forward an access-control event.

        Parameters
        ----------
        user : str
            User identifier.
        resource : str
            Resource being accessed.
        action : str
            Action attempted (e.g. ``"read"``, ``"write"``, ``"execute"``).
        allowed : bool
            Whether access was granted.
        extra : dict, optional
            Additional details.

        Returns
        -------
        bool
        """
        details: Dict[str, Any] = {
            "category": "access",
            "user": user,
            "resource": resource,
            "action": action,
            "allowed": allowed,
            "severity": "info" if allowed else "warning",
        }
        if extra:
            details.update(extra)
        return await self.forward_event("access", details)

    async def forward_anomaly_event(
        self,
        anomaly_type: str,
        description: str,
        severity: str = "warning",
        extra: dict | None = None,
    ) -> bool:
        """Forward a security anomaly event.

        Parameters
        ----------
        anomaly_type : str
            Type of anomaly (e.g. ``"brute_force"``, ``"privilege_escalation"``).
        description : str
            Human-readable description.
        severity : str
            ``"info"``, ``"warning"``, or ``"critical"``.
        extra : dict, optional
            Additional details.

        Returns
        -------
        bool
        """
        details: Dict[str, Any] = {
            "category": "anomaly",
            "anomaly_type": anomaly_type,
            "description": description,
            "severity": severity,
        }
        if extra:
            details.update(extra)
        return await self.forward_event("anomaly", details)

    async def forward_data_event(
        self,
        user: str,
        data_type: str,
        action: str,
        record_count: int = 0,
        extra: dict | None = None,
    ) -> bool:
        """Forward a data access / mutation event.

        Parameters
        ----------
        user : str
            User identifier.
        data_type : str
            Type of data (e.g. ``"project"``, ``"study_result"``).
        action : str
            Action (``"read"``, ``"create"``, ``"update"``, ``"delete"``).
        record_count : int
            Number of records affected.
        extra : dict, optional
            Additional details.

        Returns
        -------
        bool
        """
        details: Dict[str, Any] = {
            "category": "data",
            "user": user,
            "data_type": data_type,
            "action": action,
            "record_count": record_count,
            "severity": "info",
        }
        if extra:
            details.update(extra)
        return await self.forward_event("data", details)

    # -- flush / send --------------------------------------------------------

    async def flush(self) -> bool:
        """Flush buffered events to the SIEM endpoint.

        Returns
        -------
        bool
            ``True`` if all events were sent successfully.
        """
        with self._lock:
            if not self._buffer:
                return True
            batch = list(self._buffer)
            self._buffer.clear()

        if not batch:
            return True

        success = True
        for i in range(0, len(batch), self.batch_size):
            chunk = batch[i : i + self.batch_size]
            sent = await self._send_with_retry(chunk)
            if not sent:
                # Re-buffer failed events
                with self._lock:
                    for event in chunk:
                        if len(self._buffer) < self.buffer_size:
                            self._buffer.append(event)
                            self._stats["buffered"] += 1
                            self._stats["total_buffered"] += 1
                        else:
                            self._stats["dropped"] += 1
                success = False

        return success

    async def _send_with_retry(self, events: List[SecurityEvent]) -> bool:
        """Send a batch of events with exponential back-off retry.

        Parameters
        ----------
        events : list[SecurityEvent]
            Events to send.

        Returns
        -------
        bool
        """
        delay = self.retry_delay_seconds
        for attempt in range(1, self.retry_attempts + 1):
            try:
                await self._send_batch(events)
                with self._lock:
                    self._stats["forwarded"] += len(events)
                    # Derive current buffer count from the actual buffer
                    # length instead of decrementing, to avoid drift when
                    # events are re-buffered after a failed send.
                    self._stats["buffered"] = len(self._buffer)
                return True
            except Exception as exc:
                logger.warning(
                    "SIEM forward attempt %d/%d failed: %s",
                    attempt,
                    self.retry_attempts,
                    exc,
                )
                if attempt < self.retry_attempts:
                    import asyncio

                    await asyncio.sleep(delay)
                    delay *= 2

        with self._lock:
            self._stats["failed"] += len(events)
        logger.error(
            "SIEM forward failed after %d attempts for %d events", self.retry_attempts, len(events)
        )
        return False

    async def _send_batch(self, events: List[SecurityEvent]) -> None:
        """Send a batch of events to the SIEM endpoint.

        Formats the payload according to the configured *siem_type* and
        dispatches via the best available async HTTP client.

        Raises
        ------
        Exception
            If the HTTP request fails with a non-2xx status.
        """
        if self.siem_type == "loki":
            payload = self._build_loki_payload(events)
        else:
            payload = self._build_elk_payload(events)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if _HAS_HTTPX:
            await self._send_httpx(payload, headers)
        elif _HAS_AIOHTTP:
            await self._send_aiohttp(payload, headers)
        else:
            await self._send_urllib(payload, headers)

    # -- HTTP clients --------------------------------------------------------

    async def _send_httpx(self, payload: bytes, headers: Dict[str, str]) -> None:
        """Send using ``httpx.AsyncClient``."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(self.endpoint, content=payload, headers=headers)
            response.raise_for_status()

    async def _send_aiohttp(self, payload: bytes, headers: Dict[str, str]) -> None:
        """Send using ``aiohttp.ClientSession``."""
        async with aiohttp.ClientSession() as session:
            async with session.post(self.endpoint, data=payload, headers=headers) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise RuntimeError(f"SIEM returned {response.status}: {text}")

    async def _send_urllib(self, payload: bytes, headers: Dict[str, str]) -> None:
        """Fallback: send using stdlib ``urllib`` in a thread.

        This is blocking, so we offload it via :func:`asyncio.to_thread`.
        """
        import asyncio
        import urllib.request

        def _blocking_post() -> None:
            req = urllib.request.Request(
                self.endpoint, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status >= 400:
                    raise RuntimeError(f"SIEM returned {resp.status}")

        await asyncio.to_thread(_blocking_post)

    # -- Payload builders ----------------------------------------------------

    def _build_loki_payload(self, events: List[SecurityEvent]) -> bytes:
        """Build a Grafana Loki push payload.

        Each event becomes a log entry under a common set of labels.
        """
        labels_dict = {
            "source": "etap-ai-platform",
            **self.labels,
        }

        entries = []
        for event in events:
            entries.append(
                {
                    "ts": event.timestamp,
                    "line": event.to_json(),
                }
            )

        payload = {
            "streams": [
                {
                    "stream": labels_dict,
                    "values": [[e["ts"], e["line"]] for e in entries],
                }
            ]
        }
        return json.dumps(payload, default=str).encode("utf-8")

    def _build_elk_payload(self, events: List[SecurityEvent]) -> bytes:
        """Build an Elasticsearch bulk-index payload.

        Each event is prefixed with an ``index`` action line.
        """
        lines: List[str] = []
        for event in events:
            action = {"index": {"_index": f"etap-security-{datetime.now(UTC).strftime('%Y.%m.%d')}"}}
            lines.append(json.dumps(action))
            lines.append(event.to_json())
        payload = "\n".join(lines) + "\n"
        return payload.encode("utf-8")

    # -- Stats / management --------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return forwarding statistics.

        Returns
        -------
        dict
            ``{"forwarded", "failed", "buffered", "dropped", "buffer_size"}``
        """
        with self._lock:
            return {
                "forwarded": self._stats["forwarded"],
                "failed": self._stats["failed"],
                "buffered": len(self._buffer),
                "total_buffered": self._stats["total_buffered"],
                "dropped": self._stats["dropped"],
                "buffer_size": self.buffer_size,
                "siem_type": self.siem_type,
                "endpoint": self.endpoint,
            }

    async def health_check(self) -> Dict[str, Any]:
        """Perform a lightweight health check against the SIEM endpoint.

        Returns
        -------
        dict
            ``{"healthy": bool, "endpoint": str, "latency_ms": float}``
        """

        start = time.monotonic()
        try:
            if _HAS_HTTPX:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(self.endpoint.rsplit("/", 1)[0] + "/ready", timeout=5.0)
                    healthy = resp.status_code < 400
            elif _HAS_AIOHTTP:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        self.endpoint.rsplit("/", 1)[0] + "/ready",
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as resp:
                        healthy = resp.status < 400
            else:
                healthy = True  # no way to check; assume OK
        except Exception:
            healthy = False

        latency = (time.monotonic() - start) * 1000
        return {
            "healthy": healthy,
            "endpoint": self.endpoint,
            "latency_ms": round(latency, 2),
        }


# ---------------------------------------------------------------------------
# Singleton helpers
# ---------------------------------------------------------------------------

_forwarder_instance: SIEMForwarder | None = None
_forwarder_lock = threading.Lock()


def get_siem_forwarder() -> SIEMForwarder | None:
    """Get or create the global :class:`SIEMForwarder` singleton.

    Configuration is read from environment variables:

    - ``SIEM_ENDPOINT`` — ingestion URL (required to create forwarder).
    - ``SIEM_API_KEY`` — optional Bearer token.
    - ``SIEM_TYPE`` — ``"loki"`` or ``"elk"`` (default ``"loki"``).

    Returns
    -------
    SIEMForwarder or None
        ``None`` if ``SIEM_ENDPOINT`` is not configured.
    """
    global _forwarder_instance
    if _forwarder_instance is not None:
        return _forwarder_instance

    with _forwarder_lock:
        if _forwarder_instance is not None:
            return _forwarder_instance

        endpoint = os.environ.get("SIEM_ENDPOINT", "")
        if not endpoint:
            logger.info("SIEM_ENDPOINT not configured; SIEM forwarding disabled")
            return None

        api_key = os.environ.get("SIEM_API_KEY", "")
        siem_type = os.environ.get("SIEM_TYPE", "loki")

        _forwarder_instance = SIEMForwarder(
            endpoint=endpoint,
            api_key=api_key,
            siem_type=siem_type,
        )
        logger.info("SIEM forwarder initialized: type=%s endpoint=%s", siem_type, endpoint)
        return _forwarder_instance
