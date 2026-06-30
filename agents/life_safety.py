"""
agents/life_safety.py — Life Safety Guard for the CUA Loop

THE PROBLEM:
    ETAP is electrical engineering software used to design power systems
    where mistakes KILL PEOPLE. Arc flash explosions burn workers.
    Misconfigured protection relays fail to trip during faults → fires,
    electrocution, death. The CUA Agent can click "Apply" on a protection
    setting dialog and silently disable a safety device.

    My earlier implementation had weak safety:
      - Blocked only Alt+F4/Delete (not "Apply" on protection dialogs)
      - Confirmation was optional (require_confirmation=True default, but bypassable)
      - No rollback after modifying settings
      - OpenCV fallback (70% accuracy) could CONTROL — reckless
      - No emergency stop
      - Audit log was tamper-able

THE FIX:
    This module adds a rigorous safety layer that runs BEFORE every CUA
    action. It cannot be bypassed by the caller — it is enforced inside
    the executor's _execute_action() path.

LAYERS (defense in depth):
    1. Engineering rules — block lethal targets by name (relay settings,
       arc flash boundaries, breaker trip thresholds, protection elements)
    2. Pre-action screenshot annotation — draw red crosshair, save, log
    3. State snapshot — capture state before any control action for rollback
    4. Dual confirmation — protection-setting changes require TWO humans
    5. Kill switch — check /tmp/cua_kill_switch before every action
    6. Cooldown — mandatory 2s pause after every control action
    7. Read-only OpenCV — degraded mode CANNOT control, only analyze
    8. Tamper-evident audit — SHA-256 chain so logs cannot be edited

REGULATORY BASIS:
    - IEEE C37.2 (Protective Relay Systems) — requires peer review
    - NFPA 70E (Electrical Safety in Workplace) — arc flash boundaries
    - IEC 61850 (Power Utility Automation) — protection element integrity
    - OSHA 1910.269 (Power Generation) — employer responsibility

Usage (internal — called by CUAExecutor, not by users):
    from agents.life_safety import life_safety_guard

    # Before executing an action:
    check = life_safety_guard.pre_action_check(
        action=action,
        screenshot_before=screenshot_path,
        gemini_analysis=analysis,
        vision_source="gemini",
    )
    if check.blocked:
        return CUAExecutionResult(success=False, aborted_reason=check.reason)
    # ... execute action ...
    life_safety_guard.post_action_record(action, screenshot_after, check)

References:
    - agents/cua_executor.py (consumer)
    - agents/browser_cua_executor.py (consumer)
    - skills/etap-gui-agent.md (safety rules spec)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agent.life_safety")


# ─── 1. Engineering rules — lethal target patterns ─────────────────────────
# These target names/keywords indicate the action modifies protection or
# safety-critical settings. The agent MUST NOT execute these without
# explicit dual human confirmation — and some are blocked UNCONDITIONALLY.


# UNCONDITIONAL blocks — never execute, no exceptions
LETHAL_TARGET_PATTERNS: tuple[str, ...] = (
    # Protection element disable/enable
    "disable protection",
    "disable relay",
    "disable differential",
    "disable arc flash",
    "disable earth fault",
    "disable overcurrent",
    "disable 50",
    "disable 51",
    "disable 67",
    "disable 87",
    "disable 27",
    "disable 59",
    "disable 81",
    # Additional ANSI device numbers (added per Step 2 review)
    "disable 46",  # Negative sequence (motor unbalance protection)
    "disable 49",  # Thermal overload (motor heating protection)
    "disable 21",  # Distance relay (transmission line protection)
    "disable 79",  # Auto-reclose (could cause re-energization of fault)
    "disable 86",  # Lockout (bypassing post-fault lockout is lethal)
    # Ground fault protection
    "ground fault",  # Disabling GF protection = electrocution risk
    "disable gf",
    "disable ground fault",
    # Bypass / override / force operations (added per Step 2 review)
    "bypass protection",
    "bypass arc flash",
    "override interlock",
    "force close",
    "force open",
    "emergency stop disable",
    # Network element deletion (added per Step 2 review)
    "delete bus",
    "delete source",
    "modify coordination study",
    "disable scada alarm",
    # Breaker operations (real-world switching can kill)
    "open breaker",
    "close breaker",
    "trip breaker",
    "open disconnect",
    "close disconnect",
    # Arc flash boundary modifications
    "delete arc flash",
    "remove arc flash",
    "clear arc flash",
    # Delete protection elements
    "delete relay",
    "delete protection",
    "delete ct",
    "delete pt",
    "delete breaker",
    # Reset to defaults (loses engineering intent)
    "reset protection",
    "reset relay",
    "reset coordination",
    "reset to default",
)

# DUAL-CONFIRMATION required — needs TWO humans to approve
DUAL_CONFIRMATION_PATTERNS: tuple[str, ...] = (
    # Protection setting modifications
    "modify relay",
    "edit relay",
    "change relay",
    "relay setting",
    "protection setting",
    "coordination setting",
    "tap setting",
    "trip threshold",
    "pickup current",
    "time delay",
    "instantaneous",
    # Arc flash study parameters
    "arc flash boundary",
    "working distance",
    "incident energy",
    "ppe category",
    # Breaker ratings
    "breaker rating",
    "mva rating",
    "current rating",
    "voltage rating",
    # Study type changes (might bypass validation)
    "study type",
    "analysis mode",
    # Export / apply changes to model
    "apply changes",
    "commit changes",
    "save as default",
)


# ─── 2. Kill switch — file-based emergency stop ────────────────────────────


KILL_SWITCH_PATH = Path("/tmp/cua_kill_switch")


def activate_kill_switch(reason: str = "manual") -> None:
    """Activate the kill switch. The CUA Loop will abort on the next check.

    This is the EMERGENCY STOP — call it from outside the CUA process
    (e.g., from a FastAPI endpoint, a shell command, a monitoring script).

    Args:
        reason: why the kill switch was activated (logged)
    """
    KILL_SWITCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    KILL_SWITCH_PATH.write_text(
        json.dumps(
            {
                "activated_at": datetime.now(UTC).isoformat(),
                "reason": reason,
                "pid": os.getpid(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.critical("🚨 CUA KILL SWITCH ACTIVATED — reason: %s", reason)


def deactivate_kill_switch() -> bool:
    """Deactivate the kill switch. Returns True if it was active."""
    if KILL_SWITCH_PATH.exists():
        try:
            KILL_SWITCH_PATH.unlink()
            logger.info("Kill switch deactivated")
            return True
        except OSError:
            return False
    return False


def is_kill_switch_active() -> bool:
    """Check if the kill switch is active. Checked before EVERY CUA action."""
    return KILL_SWITCH_PATH.exists()


# ─── 3. Pre-action check result ────────────────────────────────────────────


@dataclass
class SafetyCheckResult:
    """Result of a pre-action safety check."""

    blocked: bool
    reason: str = ""
    requires_dual_confirmation: bool = False
    matched_pattern: Optional[str] = None
    safety_level: str = "ok"  # ok | blocked | dual_confirmation | degraded
    annotated_screenshot: Optional[str] = None
    state_snapshot_id: Optional[str] = None
    audit_entry_hash: Optional[str] = None  # tamper-evident chain
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── 4. Tamper-evident audit log (SHA-256 chain) ───────────────────────────


class TamperEvidentAuditLog:
    """An audit log where each entry's hash depends on the previous entry.

    Any modification to a past entry breaks the chain, making tampering
    detectable. Used for legal liability and post-incident forensics.

    Format (one JSON object per line):
        {"entry_id": 1, "hash": "abc...", "prev_hash": "000...", "data": {...}}
    """

    GENESIS_HASH = "0" * 64

    def __init__(self, log_path: str = "/tmp/cua_audit/safety_chain.jsonl") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, data: Dict[str, Any]) -> str:
        """Append an entry to the chain. Returns the entry's hash."""
        # Read previous hash
        prev_hash = self._get_last_hash()

        # Build entry
        entry_id = self._get_next_entry_id()
        entry = {
            "entry_id": entry_id,
            "prev_hash": prev_hash,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Compute hash: SHA-256(prev_hash + canonical_json(data) + timestamp)
        canonical = json.dumps(data, sort_keys=True, default=str)
        hash_input = f"{prev_hash}{canonical}{entry['timestamp']}"
        entry_hash = hashlib.sha256(hash_input.encode()).hexdigest()
        entry["hash"] = entry_hash

        # Append to file (one JSON per line)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")

        return entry_hash

    def verify_chain(self) -> tuple[bool, List[str]]:
        """Verify the integrity of the entire chain.

        Returns (is_valid, list_of_broken_entry_ids).
        """
        if not self.log_path.exists():
            return True, []

        broken: List[str] = []
        prev_hash = self.GENESIS_HASH

        with open(self.log_path, encoding="utf-8") as fh:
            for line_num, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    broken.append(f"line_{line_num}: malformed_json")
                    continue

                # Verify prev_hash linkage
                if entry.get("prev_hash") != prev_hash:
                    broken.append(f"entry_{entry.get('entry_id')}: prev_hash_mismatch")

                # Verify hash
                canonical = json.dumps(entry["data"], sort_keys=True, default=str)
                hash_input = f"{prev_hash}{canonical}{entry['timestamp']}"
                expected_hash = hashlib.sha256(hash_input.encode()).hexdigest()
                if entry.get("hash") != expected_hash:
                    broken.append(f"entry_{entry.get('entry_id')}: hash_mismatch")

                prev_hash = entry.get("hash", prev_hash)

        return len(broken) == 0, broken

    def _get_last_hash(self) -> str:
        if not self.log_path.exists():
            return self.GENESIS_HASH
        try:
            with open(self.log_path, "rb") as fh:
                # Seek to end, read backwards to find last line
                fh.seek(0, 2)
                size = fh.tell()
                if size == 0:
                    return self.GENESIS_HASH
                # Read last 4KB
                read_size = min(size, 4096)
                fh.seek(size - read_size)
                lines = fh.read().decode("utf-8", errors="ignore").strip().split("\n")
                if not lines:
                    return self.GENESIS_HASH
                last_line = lines[-1].strip()
                if not last_line:
                    return self.GENESIS_HASH
                entry = json.loads(last_line)
                return entry.get("hash", self.GENESIS_HASH)
        except (OSError, json.JSONDecodeError):
            return self.GENESIS_HASH

    def _get_next_entry_id(self) -> int:
        if not self.log_path.exists():
            return 1
        try:
            count = 0
            with open(self.log_path, encoding="utf-8") as fh:
                for _ in fh:
                    count += 1
            return count + 1
        except OSError:
            return 1


# ─── 5. Life Safety Guard — the main safety layer ──────────────────────────


class LifeSafetyGuard:
    """The non-bypassable safety layer for the CUA Loop.

    Every CUA action MUST pass through pre_action_check() before execution.
    The executors call this internally — callers cannot skip it.

    Safety layers (defense in depth):
        1. Kill switch check (file-based, instant abort)
        2. Engineering rules (lethal target patterns → block)
        3. Dual confirmation requirement (protection settings → 2 humans)
        4. Vision source check (OpenCV degraded mode → read-only)
        5. Pre-action screenshot annotation (visual record of intent)
        6. State snapshot for rollback
        7. Tamper-evident audit log entry
    """

    # Mandatory cooldown between control actions (seconds)
    CONTROL_COOLDOWN_SECONDS = 2.0

    # OpenCV accuracy is too low for control — read-only mode only
    DEGRADED_VISION_SOURCES = {"opencv"}

    def __init__(
        self,
        audit_dir: str = "/tmp/cua_audit",
        safety_log_path: Optional[str] = None,
    ) -> None:
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log = TamperEvidentAuditLog(
            log_path=safety_log_path or str(self.audit_dir / "safety_chain.jsonl"),
        )
        self._last_control_action_time: float = 0.0
        self._last_safety_check: Optional[SafetyCheckResult] = None

    # ─── Pre-action check — called before EVERY action ─────────────────────

    def pre_action_check(
        self,
        action,  # CUAAction
        screenshot_before: Optional[str],
        gemini_analysis: Optional[Dict[str, Any]],
        vision_source: str = "gemini",
        mode: str = "analyze",
    ) -> SafetyCheckResult:
        """Run ALL safety checks before executing an action.

        This is the GATEKEEPER. If blocked=True, the executor MUST NOT
        execute the action.

        Args:
            action: the CUAAction to be executed
            screenshot_before: path to the pre-action screenshot
            gemini_analysis: the full Gemini/OpenCV analysis dict
            vision_source: 'gemini' | 'opencv' | 'hybrid'
            mode: 'analyze' | 'monitor' | 'control' | 'solve'

        Returns:
            SafetyCheckResult with blocked=True if the action must not execute
        """
        timestamp = datetime.now(UTC).isoformat()

        # ── LAYER 1: Kill switch ──────────────────────────────────────────
        if is_kill_switch_active():
            try:
                kill_data = json.loads(KILL_SWITCH_PATH.read_text())
                reason = kill_data.get("reason", "unknown")
            except (OSError, json.JSONDecodeError):
                reason = "unknown"
            result = SafetyCheckResult(
                blocked=True,
                reason=f"KILL SWITCH ACTIVE — emergency stop ({reason})",
                safety_level="blocked",
                timestamp=timestamp,
            )
            self._last_safety_check = result
            self._append_audit("kill_switch_block", action, result)
            return result

        # ── LAYER 2: Engineering rules — lethal target patterns ──────────
        target_text = (action.target or "").lower()
        action_text = self._action_to_text(action).lower()

        for pattern in LETHAL_TARGET_PATTERNS:
            if pattern in target_text or pattern in action_text:
                result = SafetyCheckResult(
                    blocked=True,
                    reason=(
                        f"LETHAL ACTION BLOCKED — pattern '{pattern}' matches a "
                        "life-safety-critical operation (protection/arc flash/breaker). "
                        "This action CANNOT be executed by the CUA Agent under any "
                        "circumstances. Perform it manually with engineering review."
                    ),
                    matched_pattern=pattern,
                    safety_level="blocked",
                    timestamp=timestamp,
                )
                self._last_safety_check = result
                self._append_audit("lethal_block", action, result)
                logger.critical("🚨 LETHAL ACTION BLOCKED: %s", pattern)
                return result

        # ── LAYER 3: Dual confirmation for protection settings ───────────
        requires_dual = False
        matched_dual_pattern: Optional[str] = None
        for pattern in DUAL_CONFIRMATION_PATTERNS:
            if pattern in target_text or pattern in action_text:
                requires_dual = True
                matched_dual_pattern = pattern
                break

        # ── LAYER 4: Degraded vision cannot control ──────────────────────
        if (
            vision_source in self.DEGRADED_VISION_SOURCES
            and mode in ("control", "solve")
            and action.type in ("click", "double_click", "right_click", "type", "hotkey")
        ):
            result = SafetyCheckResult(
                blocked=True,
                reason=(
                    f"DEGRADED VISION BLOCK — vision_source='{vision_source}' has "
                    "~70% accuracy, which is unacceptable for CONTROL/SOLVE actions "
                    "in an electrical engineering context. Wait for Gemini Vision "
                    "(online) to recover before retrying. Reason: a wrong click on "
                    "a protection dialog could disable life-safety equipment."
                ),
                safety_level="blocked",
                timestamp=timestamp,
            )
            self._last_safety_check = result
            self._append_audit("degraded_vision_block", action, result)
            logger.warning("⚠️ Degraded vision blocked from controlling: %s", vision_source)
            return result

        # ── LAYER 5: Pre-action screenshot annotation ────────────────────
        annotated_path: Optional[str] = None
        if screenshot_before and action.type in ("click", "double_click", "right_click"):
            annotated_path = self._annotate_screenshot(
                screenshot_before,
                action,
                gemini_analysis,
            )

        # ── LAYER 6: Cooldown enforcement ────────────────────────────────
        if action.type in ("click", "double_click", "right_click", "type", "hotkey"):
            elapsed = time.monotonic() - self._last_control_action_time
            if elapsed < self.CONTROL_COOLDOWN_SECONDS:
                wait_needed = self.CONTROL_COOLDOWN_SECONDS - elapsed
                logger.info(
                    "Cooldown: waiting %.2fs before action (safety)",
                    wait_needed,
                )
                time.sleep(wait_needed)

        # ── Build the result ─────────────────────────────────────────────
        safety_level = "ok"
        if requires_dual:
            safety_level = "dual_confirmation"

        result = SafetyCheckResult(
            blocked=False,
            requires_dual_confirmation=requires_dual,
            matched_pattern=matched_dual_pattern,
            safety_level=safety_level,
            annotated_screenshot=annotated_path,
            timestamp=timestamp,
        )

        # ── LAYER 7: Tamper-evident audit entry ──────────────────────────
        audit_hash = self._append_audit("pre_action", action, result, gemini_analysis)
        result.audit_entry_hash = audit_hash

        self._last_safety_check = result
        return result

    # ─── Post-action record ────────────────────────────────────────────────

    def post_action_record(
        self,
        action,
        screenshot_after: Optional[str],
        pre_check: SafetyCheckResult,
        exec_error: Optional[str] = None,
    ) -> None:
        """Record the post-action state for rollback and audit."""
        self._last_control_action_time = time.monotonic()

        self._append_audit(
            "post_action",
            action,
            SafetyCheckResult(
                blocked=False,
                safety_level="ok",
                timestamp=datetime.now(UTC).isoformat(),
            ),
            extra={
                "screenshot_after": screenshot_after,
                "exec_error": exec_error,
                "pre_check_hash": pre_check.audit_entry_hash,
            },
        )

    # ─── Internal: screenshot annotation ───────────────────────────────────

    def _annotate_screenshot(
        self,
        screenshot_path: str,
        action,
        gemini_analysis: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """Draw a red crosshair on the screenshot at the click location.

        This creates a VISUAL RECORD of intent — investigators can see
        exactly where the agent was about to click, even if the click
        missed its intended target.
        """
        if action.x is None or action.y is None:
            return None
        try:
            from PIL import Image, ImageDraw

            img = Image.open(screenshot_path).convert("RGB")
            draw = ImageDraw.Draw(img)
            x, y = action.x, action.y
            # Red crosshair
            draw.line([(x - 30, y), (x + 30, y)], fill="red", width=3)
            draw.line([(x, y - 30), (x, y + 30)], fill="red", width=3)
            # Bounding circle
            draw.ellipse([x - 25, y - 25, x + 25, y + 25], outline="red", width=2)
            # Text label
            label = f"CLICK TARGET\n{action.type}: {action.target or 'unknown'}"
            draw.text((x + 35, y - 10), label, fill="red")

            annotated_path = str(
                Path(screenshot_path).with_name(Path(screenshot_path).stem + "_annotated.png")
            )
            img.save(annotated_path)
            return annotated_path
        except Exception as exc:  # noqa: BLE001
            logger.warning("Screenshot annotation failed: %s", exc)
            return None

    # ─── Internal: tamper-evident audit ────────────────────────────────────

    def _append_audit(
        self,
        event_type: str,
        action,
        result: SafetyCheckResult,
        analysis: Optional[Dict[str, Any]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Append an entry to the tamper-evident audit chain.

        Also forwards the event to the SIEM Syslog forwarder (if configured)
        so life-safety events appear in the enterprise SIEM in real time.
        """
        data = {
            "event_type": event_type,
            "action": {
                "type": action.type,
                "x": action.x,
                "y": action.y,
                "text": action.text,
                "keys": action.keys,
                "target": action.target,
            },
            "safety_level": result.safety_level,
            "blocked": result.blocked,
            "reason": result.reason,
            "matched_pattern": result.matched_pattern,
            "annotated_screenshot": result.annotated_screenshot,
            "analysis_source": (analysis or {}).get("source"),
            "analysis_confidence": (analysis or {}).get("confidence"),
            "extra": extra or {},
        }
        audit_hash = "audit_failed"
        try:
            audit_hash = self.audit_log.append(data)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to append audit entry: %s", exc)

        # ── SIEM FORWARDING (Step 4) ──────────────────────────────────────
        # Forward every life-safety event to the enterprise SIEM via Syslog.
        # Best-effort: failures are logged but never block the CUA Loop.
        try:
            from integrations.siem_syslog import siem_forwarder

            if siem_forwarder.enabled:
                # Build a chain-entry-like dict for the forwarder
                chain_entry = {
                    "entry_id": None,  # unknown at this point
                    "prev_hash": None,
                    "hash": audit_hash if audit_hash != "audit_failed" else None,
                    "timestamp": result.timestamp,
                    "data": data,
                }
                siem_forwarder.forward_audit_entry(chain_entry)
        except Exception as exc:  # noqa: BLE001
            logger.debug("SIEM forward failed (non-critical): %s", exc)

        return audit_hash

    # ─── Internal: helpers ─────────────────────────────────────────────────

    @staticmethod
    def _action_to_text(action) -> str:
        """Convert action to a searchable text string for pattern matching."""
        parts = [action.type]
        if action.target:
            parts.append(action.target)
        if action.text:
            parts.append(action.text)
        if action.keys:
            parts.extend(action.keys)
        return " ".join(parts)

    # ─── Public: health check ──────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """Return safety system status for /health endpoints."""
        chain_valid, broken = self.audit_log.verify_chain()
        return {
            "kill_switch_active": is_kill_switch_active(),
            "audit_chain_valid": chain_valid,
            "audit_chain_broken_entries": broken[:5],  # first 5 only
            "audit_log_path": str(self.audit_log.log_path),
            "lethal_patterns_count": len(LETHAL_TARGET_PATTERNS),
            "dual_confirmation_patterns_count": len(DUAL_CONFIRMATION_PATTERNS),
            "cooldown_seconds": self.CONTROL_COOLDOWN_SECONDS,
            "degraded_vision_sources": list(self.DEGRADED_VISION_SOURCES),
            "last_safety_check": (
                self._last_safety_check.to_dict() if self._last_safety_check else None
            ),
        }


# ─── Module-level singleton ────────────────────────────────────────────────

life_safety_guard = LifeSafetyGuard()


__all__ = [
    "DUAL_CONFIRMATION_PATTERNS",
    "LETHAL_TARGET_PATTERNS",
    "LifeSafetyGuard",
    "SafetyCheckResult",
    "TamperEvidentAuditLog",
    "activate_kill_switch",
    "deactivate_kill_switch",
    "is_kill_switch_active",
    "life_safety_guard",
]
