"""
integrations/siem_syslog.py — Syslog RFC 5424 integration for SIEM forwarding

Forwards life-safety audit events from the CUA Loop to a SIEM system
(Splunk, IBM QRadar, Google Chronicle, ArcSight) via standard Syslog.

WHY SYSLOG:
    Syslog (RFC 5424) is the de facto standard for security event
    forwarding. Almost every SIEM accepts it natively, making this
    integration work with any enterprise SIEM without vendor lock-in.

WHAT IT FORWARDS:
    - Every life-safety audit entry (from the SHA-256 chain)
    - Kill switch activations
    - Lethal action blocks
    - Dual confirmation requests and resolutions
    - Degraded vision blocks

TRANSPORT:
    - UDP (default, port 514) — fast, no handshake, may lose packets
    - TCP (optional, port 514) — reliable, but blocks if SIEM is down
    - TLS (optional, port 6514) — encrypted, for sensitive environments

CONFIGURATION (env vars):
    SIEM_ENABLED=true                    — enable forwarding (default: false)
    SIEM_HOST=10.0.0.100                 — SIEM server hostname/IP
    SIEM_PORT=514                        — SIEM port (default: 514)
    SIEM_PROTOCOL=udp                    — udp | tcp | tls
    SIEM_FACILITY=local0                 — syslog facility (default: local0)
    SIEM_SEVERITY=warning                — emergency|alert|critical|warning|info|debug
    SIEM_APP_NAME=AhmedETAP-CUA          — app name in syslog header
    SIEM_TLS_CA_CERT=/path/to/ca.pem     — for TLS only

USAGE:
    from integrations.siem_syslog import siem_forwarder

    # Forward a single event
    siem_forwarder.forward({
        "event_type": "lethal_block",
        "action": {"type": "click", "target": "disable protection"},
        "reason": "LETHAL ACTION BLOCKED",
        "audit_hash": "abc123...",
    })

    # Forward an entire audit chain entry
    siem_forwarder.forward_audit_entry(chain_entry_dict)

REFERENCES:
    - RFC 5424: https://tools.ietf.org/html/rfc5424
    - agents/life_safety.py (audit chain source)
    - Splunk Universal Forwarder accepts syslog on port 514
    - IBM QRadar accepts syslog on port 514
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import socket
import ssl
import threading
from datetime import UTC
from typing import Any

logger = logging.getLogger(__name__)


# ─── Syslog severity levels (RFC 5424) ─────────────────────────────────────

SYSLOG_SEVERITY = {
    "emergency": 0,  # System is unusable
    "alert": 1,  # Action must be taken immediately
    "critical": 2,  # Critical conditions
    "error": 3,  # Error conditions
    "warning": 4,  # Warning conditions
    "notice": 5,  # Normal but significant condition
    "info": 6,  # Informational messages
    "debug": 7,  # Debug-level messages
}

SYSLOG_FACILITY = {
    "kern": 0,
    "user": 1,
    "mail": 2,
    "daemon": 3,
    "auth": 4,
    "syslog": 5,
    "lpr": 6,
    "news": 7,
    "uucp": 8,
    "cron": 9,
    "authpriv": 10,
    "ftp": 11,
    "ntp": 12,
    "audit": 13,
    "alert": 14,
    "clock": 15,
    "local0": 16,
    "local1": 17,
    "local2": 18,
    "local3": 19,
    "local4": 20,
    "local5": 21,
    "local6": 22,
    "local7": 23,
}

# Map our event types to syslog severity
EVENT_SEVERITY_MAP = {
    "kill_switch_block": "alert",  # emergency stop triggered
    "lethal_block": "critical",  # lethal action attempted
    "degraded_vision_block": "warning",  # degraded mode blocked control
    "dual_confirmation_request": "notice",  # awaiting 2 humans
    "dual_confirmation_resolved": "info",  # approved/rejected
    "pre_action": "info",  # action about to execute
    "post_action": "info",  # action completed
    "audit_tamper_detected": "emergency",  # audit chain broken
}


# ─── Syslog Forwarder ──────────────────────────────────────────────────────


class SIEMSyslogForwarder:
    """Forwards life-safety events to a SIEM via Syslog RFC 5424.

    Singleton pattern — one forwarder per process.
    """

    def __init__(self) -> None:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self.enabled = os.getenv("SIEM_ENABLED", "false").lower() == "true"
        self.host = os.getenv("SIEM_HOST", "")
        self.port = int(os.getenv("SIEM_PORT", "514"))
        self.protocol = os.getenv("SIEM_PROTOCOL", "udp").lower()
        self.facility_name = os.getenv("SIEM_FACILITY", "local0")
        self.default_severity = os.getenv("SIEM_SEVERITY", "warning")
        self.app_name = os.getenv("SIEM_APP_NAME", "AhmedETAP-CUA")
        self.hostname = socket.gethostname() or "unknown"
        self.tls_ca_cert = os.getenv("SIEM_TLS_CA_CERT", "")

        # ─── LOGGING-ONLY MODE (no SIEM server needed) ─────────────────────
        # When SIEM_LOG_FILE is set, events are written to a local JSONL file
        # instead of being sent over the network. Useful for:
        #   - Testing without a SIEM server
        #   - HF Space (which has no inbound network access)
        #   - Local forensic logging
        self.log_file = os.getenv("SIEM_LOG_FILE", "")
        self.logging_only = bool(self.log_file) and self.protocol == "file"

        # If SIEM_LOG_FILE is set, enable in logging-only mode automatically
        if self.log_file and not self.host:
            self.logging_only = True
            self.enabled = True  # enable forwarding to the local file
            self.protocol = "file"
            logger.info("SIEM in LOGGING-ONLY mode — events written to %s", self.log_file)

        # Validate config
        if self.enabled and not self.host and not self.logging_only:
            logger.warning("SIEM enabled but SIEM_HOST not set — disabling")
            self.enabled = False

        if self.facility_name not in SYSLOG_FACILITY:
            logger.warning("Unknown syslog facility '%s' — using local0", self.facility_name)
            self.facility_name = "local0"

        # Pre-compute facility code
        self._facility_code = SYSLOG_FACILITY[self.facility_name]

        # TLS context (lazy init)
        self._tls_context: ssl.SSLContext | None = None

        # Ensure log file directory exists (for logging-only mode)
        if self.logging_only and self.log_file:
            try:
                log_path = os.path.dirname(self.log_file)
                if log_path:
                    os.makedirs(log_path, exist_ok=True)
            except OSError as exc:
                logger.warning("Cannot create SIEM log dir %s: %s", log_path, exc)

        if self.enabled:
            if self.logging_only:
                logger.info(
                    "✅ SIEM LOGGING-ONLY mode — file=%s (facility=%s)",
                    self.log_file,
                    self.facility_name,
                )
            else:
                logger.info(
                    "✅ SIEM Syslog forwarder initialized — %s://%s:%d (facility=%s)",
                    self.protocol,
                    self.host,
                    self.port,
                    self.facility_name,
                )
        else:
            missing = []
            if not os.getenv("SIEM_HOST"):
                missing.append("SIEM_HOST")
            if not os.getenv("SIEM_LOG_FILE"):
                missing.append("SIEM_LOG_FILE")
            logger.info(
                "SIEM Syslog disabled — missing: %s", ", ".join(missing) or "SIEM_ENABLED=false",
            )

    # ─── Public API ───────────────────────────────────────────────────────

    def forward(self, event: dict[str, Any]) -> bool:
        """Forward a single event dict to the SIEM.

        Args:
            event: the event data (must contain 'event_type')

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.enabled:
            return False

        event_type = event.get("event_type", "unknown")
        severity_name = EVENT_SEVERITY_MAP.get(event_type, self.default_severity)
        severity_code = SYSLOG_SEVERITY.get(severity_name, SYSLOG_SEVERITY["warning"])

        # Build the syslog message
        message = self._format_syslog_message(
            facility=self._facility_code,
            severity=severity_code,
            msg_id=event_type,
            structured_data=event,
            message=self._build_human_message(event),
        )

        return self._send(message)

    def forward_audit_entry(self, chain_entry: dict[str, Any]) -> bool:
        """Forward an entry from the tamper-evident audit chain.

        Args:
            chain_entry: dict with keys: entry_id, prev_hash, hash, data, timestamp

        Returns:
            True if sent successfully.
        """
        if not self.enabled:
            return False

        data = chain_entry.get("data", {})
        event_type = data.get("event_type", "audit_entry")

        # Higher severity if the chain entry indicates a block
        if data.get("blocked"):
            severity_name = "critical"
        elif data.get("requires_dual_confirmation"):
            severity_name = "notice"
        else:
            severity_name = "info"

        severity_code = SYSLOG_SEVERITY.get(severity_name, SYSLOG_SEVERITY["info"])

        # Include the hash in structured data for SIEM correlation
        structured = {
            "audit_entry_id": chain_entry.get("entry_id"),
            "audit_hash": chain_entry.get("hash"),
            "audit_prev_hash": chain_entry.get("prev_hash"),
            "audit_timestamp": chain_entry.get("timestamp"),
            **data,
        }

        message = self._format_syslog_message(
            facility=self._facility_code,
            severity=severity_code,
            msg_id=event_type,
            structured_data=structured,
            message=f"Audit #{chain_entry.get('entry_id')} [{event_type}] hash={chain_entry.get('hash', '?')[:16]}",
        )

        return self._send(message)

    def health_check(self) -> dict[str, Any]:
        """Return forwarder status."""
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "facility": self.facility_name,
            "default_severity": self.default_severity,
            "app_name": self.app_name,
            "hostname": self.hostname,
            "tls_configured": bool(self.tls_ca_cert),
            "logging_only": self.logging_only,
            "log_file": self.log_file,
        }

    # ─── Internal: format RFC 5424 message ────────────────────────────────

    def _format_syslog_message(
        self,
        facility: int,
        severity: int,
        msg_id: str,
        structured_data: dict[str, Any],
        message: str,
    ) -> bytes:
        """Format a message according to RFC 5424.

        Format:
            <PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID SD MSG

        Example:
            <165>1 2026-06-30T12:34:56Z host01 AhmedETAP-CUA - lethal_block
            [AhmedETAP@1 action="click" target="disable protection"] LETHAL BLOCK
        """
        # PRI = facility * 8 + severity
        pri = facility * 8 + severity
        version = 1
        timestamp = datetime.datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        procid = os.getpid()

        # Structured data (SD) — single element with our app name
        sd_string = self._format_structured_data(structured_data)

        # Build the message
        # Note: NILVALUE "-" is used for missing fields per RFC 5424
        header = f"<{pri}>{version} {timestamp} {self.hostname} {self.app_name} {procid} {msg_id}"
        full_message = f"{header} {sd_string} {message}"

        return full_message.encode("utf-8")

    @staticmethod
    def _format_structured_data(data: dict[str, Any]) -> str:
        """Format structured data per RFC 5424 §6.3.

        Format: [name@enterprise param="value" param2="value2"]
        """
        if not data:
            return "-"  # NILVALUE

        # Use a simple SD-ID with our enterprise number
        sd_id = "AhmedETAP@4827"

        # Build params — escape quotes and backslashes
        params = []
        for key, value in data.items():
            if value is None:
                continue
            # Convert complex values to JSON string
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, default=str)
            else:
                value_str = str(value)
            # Escape per RFC 5424: backslash, quote, ]
            escaped = value_str.replace("\\", "\\\\").replace('"', '\\"').replace("]", "\\]")
            # Truncate to 255 chars max (RFC limit on SD-param value)
            if len(escaped) > 255:
                escaped = escaped[:252] + "..."
            params.append(f'{key}="{escaped}"')

        if not params:
            return "-"

        return f"[{sd_id} {' '.join(params)}]"

    @staticmethod
    def _build_human_message(event: dict[str, Any]) -> str:
        """Build a human-readable summary of the event."""
        event_type = event.get("event_type", "unknown")
        action = event.get("action", {})
        target = action.get("target", "?") if isinstance(action, dict) else "?"
        reason = event.get("reason", "")

        parts = [f"[{event_type}]"]
        if target and target != "?":
            parts.append(f"target={target}")
        if reason:
            # Truncate long reasons
            reason_short = reason[:120] + "..." if len(reason) > 120 else reason
            parts.append(f"reason={reason_short}")
        if event.get("audit_entry_hash"):
            parts.append(f"hash={event['audit_entry_hash'][:16]}")

        return " ".join(parts)

    # ─── Internal: send via UDP/TCP/TLS ───────────────────────────────────

    def _send(self, message: bytes) -> bool:
        """Send the syslog message via the configured protocol.

        Runs in a thread to avoid blocking the caller (UDP send is fast,
        but TCP/TLS may block if SIEM is slow).
        """
        if not self.enabled:
            return False

        # Run in a daemon thread to avoid blocking
        result: dict[str, bool] = {"sent": False}

        def _send_thread():
            try:
                if self.protocol == "file":
                    self._send_file(message)
                elif self.protocol == "udp":
                    self._send_udp(message)
                elif self.protocol == "tcp":
                    self._send_tcp(message)
                elif self.protocol == "tls":
                    self._send_tls(message)
                else:
                    logger.warning("Unknown SIEM protocol: %s", self.protocol)
                    return
                result["sent"] = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("SIEM forward failed: %s", exc)
                result["sent"] = False

        t = threading.Thread(target=_send_thread, daemon=True)
        t.start()
        t.join(timeout=5.0)  # max 5s to avoid blocking CUA loop

        return result["sent"]

    def _send_udp(self, message: bytes) -> None:
        """Send via UDP (default, fast, may lose packets)."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            # UDP messages should be < 65,507 bytes
            if len(message) > 65000:
                logger.warning(
                    "Syslog message too large for UDP (%d bytes) — truncating", len(message),
                )
                message = message[:65000]
            sock.sendto(message, (self.host, self.port))

    def _send_file(self, message: bytes) -> None:
        """LOGGING-ONLY mode — write the syslog message to a local JSONL file.

        Each line is a JSON object with:
          - timestamp: ISO 8601 UTC
          - syslog_message: the raw RFC 5424 message (decoded)
          - parsed: the structured data extracted from the message

        This is useful for:
          - Testing without a SIEM server
          - HF Space (no inbound network)
          - Local forensic logging
        """
        if not self.log_file:
            return

        # Decode the syslog message for JSON storage
        message_str = message.decode("utf-8", errors="replace")

        # Build the JSONL entry
        entry = {
            "timestamp": datetime.datetime.now(UTC).isoformat(),
            "syslog_message": message_str,
            "log_file": self.log_file,
        }

        # Append to the file (one JSON per line)
        with open(self.log_file, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

    def _send_tcp(self, message: bytes) -> None:
        """Send via TCP (reliable, but may block if SIEM is down)."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5.0)
            sock.connect((self.host, self.port))
            # Syslog over TCP: append newline as frame delimiter (RFC 6587 octet-counting optional)
            sock.sendall(message + b"\n")

    def _send_tls(self, message: bytes) -> None:
        """Send via TLS (encrypted, for sensitive environments)."""
        if self._tls_context is None:
            self._tls_context = ssl.create_default_context()
            # Harden: disable legacy protocols (TLSv1.0/1.1) explicitly.
            # Python 3.10+ defaults to TLSv1.2+, but we set it defensively
            # for older runtimes (SonarCloud S4423).
            self._tls_context.minimum_version = ssl.TLSVersion.TLSv1_2
            if self.tls_ca_cert and os.path.exists(self.tls_ca_cert):
                self._tls_context.load_verify_locations(self.tls_ca_cert)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5.0)
            with self._tls_context.wrap_socket(sock, server_hostname=self.host) as tls_sock:
                tls_sock.connect((self.host, self.port))
                tls_sock.sendall(message + b"\n")


# ─── Module-level singleton ────────────────────────────────────────────────

siem_forwarder = SIEMSyslogForwarder()


__all__ = ["SIEMSyslogForwarder", "siem_forwarder"]
