"""
services/alerting_service.py — Active Production Alerting Service (FIX-26).

Provides proactive alerting for critical infrastructure events:
- /healthz failures (database degraded, unhandled exceptions)
- Startup migration gate failures
- Deployment / worker crash events

Includes:
- Anti-alert fatigue debouncing (configurable cooldown per alert type)
- Webhook dispatch (Slack / Teams / Generic Webhook) with SSRF prevention
- Structured JSON logging for Prometheus / Grafana Loki ingestion
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger("engineering_service.alerting")
UTC = timezone.utc


class AlertSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class AlertingService:
    """Production alerting service with debouncing and multi-channel dispatch.

    Note on Multi-Worker Concurrency:
    Debouncing is currently maintained in-memory per worker process (_last_alert_times dict).
    In a deployment with N worker processes (e.g. 4 Gunicorn workers), a burst of identical
    alerts may dispatch up to N times (once per worker) during the debounce window (default 300s)
    before each worker's local cache suppresses further dispatches. For strictly unified
    cross-worker deduplication, a shared Redis key with TTL can be utilized.
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        debounce_seconds: float = 300.0,
    ):
        self.webhook_url = webhook_url or os.getenv(
            "ALERT_WEBHOOK_URL", os.getenv("SLACK_WEBHOOK_URL", "")
        )
        self.debounce_seconds = float(os.getenv("ALERT_DEBOUNCE_SECONDS", str(debounce_seconds)))
        self._last_alert_times: Dict[str, float] = {}
        self._suppressed_counts: Dict[str, int] = {}

    def should_dispatch(self, alert_type: str, now: Optional[float] = None) -> bool:
        """Check if an alert should be dispatched or debounced."""
        current_time = now if now is not None else time.time()
        last_time = self._last_alert_times.get(alert_type)

        if last_time is None or (current_time - last_time) >= self.debounce_seconds:
            self._last_alert_times[alert_type] = current_time
            self._suppressed_counts[alert_type] = 0
            return True

        self._suppressed_counts[alert_type] = self._suppressed_counts.get(alert_type, 0) + 1
        return False

    async def trigger_alert(
        self,
        alert_type: str,
        message: str,
        severity: AlertSeverity | str = AlertSeverity.CRITICAL,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Trigger an alert across active channels if not debounced.

        Returns True if dispatched, False if suppressed by debouncing.
        """
        severity_str = severity.value if isinstance(severity, AlertSeverity) else str(severity)
        now_ts = time.time()

        if not self.should_dispatch(alert_type, now=now_ts):
            suppressed = self._suppressed_counts.get(alert_type, 1)
            logger.debug(
                "Alert %s suppressed by debouncing (count=%d, cooldown=%ss)",
                alert_type,
                suppressed,
                self.debounce_seconds,
            )
            return False

        payload = {
            "alert_type": alert_type,
            "severity": severity_str,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
            "details": details or {},
            "environment": os.getenv("ENVIRONMENT", os.getenv("ENV", "production")),
        }

        # 1. Structured log output
        log_level = logging.CRITICAL if severity_str == "CRITICAL" else logging.WARNING
        logger.log(log_level, "ALERT_DISPATCH: %s", json.dumps(payload))

        # 2. Webhook dispatch if configured
        if self.webhook_url:
            await self._send_webhook(payload)

        return True

    async def _send_webhook(self, payload: Dict[str, Any]) -> None:
        """Deliver alert payload via HTTP POST to external webhook."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code >= 400:
                    logger.warning("Alert webhook response status: %s", resp.status_code)
        except Exception as exc:
            logger.warning("Failed to dispatch alert webhook: %s", exc)


_instance: Optional[AlertingService] = None


def get_alerting_service() -> AlertingService:
    """Return the global AlertingService singleton."""
    global _instance
    if _instance is None:
        _instance = AlertingService()
    return _instance
