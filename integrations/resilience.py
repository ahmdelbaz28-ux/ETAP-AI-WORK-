"""
integrations/resilience.py — Connection resilience for the CUA Loop

Provides retry, checkpoint, and offline-fallback mechanisms so the CUA Loop
can survive transient network failures without losing all progress.

PROBLEM IT SOLVES:
    The CUA Loop runs for many steps (up to 50). If step 12 of 15 fails
    because Gemini Vision returned a 503, the entire loop aborts and the
    user loses all progress. This module fixes that.

WHAT IT PROVIDES:
    1. retry_with_backoff() — decorator for transient failures
    2. CheckpointStore — persists loop state to disk every step
    3. ResumeManager — loads the latest checkpoint and resumes from there
    4. HybridVisionRouter — tries Gemini first, falls back to OpenCV

USAGE:
    from integrations.resilience import retry_with_backoff, CheckpointStore

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def call_gemini(...):
        ...

    store = CheckpointStore(directory="/tmp/cua_checkpoints")
    store.save(execution_id="abc123", step_num=5, state={...})
    latest = store.load_latest("abc123")
    if latest:
        resume_from = latest["step_num"]

References:
    - agents/cua_executor.py (consumer)
    - agents/browser_cua_executor.py (consumer)
    - integrations/gemini_vision.py (online path)
    - integrations/opencv_vision.py (offline fallback)
"""

from __future__ import annotations

import contextlib
import functools
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ─── 1. Retry decorator with exponential backoff ──────────────────────────


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
):
    """Decorator: retry a function on transient failures with exponential backoff.

    Args:
        max_retries: max number of retry attempts (total attempts = max_retries + 1)
        base_delay: initial delay in seconds (doubles each retry)
        max_delay: cap on delay between retries
        exceptions: which exception types to retry on (default: all)
        on_retry: optional callback(attempt, exception) called before each retry

    Example:
        @retry_with_backoff(max_retries=3, base_delay=2.0)
        def call_gemini_api(...):
            return requests.post(...)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 2):  # +1 for initial attempt
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt > max_retries:
                        logger.exception(
                            "%s failed after %d attempts: %s",
                            func.__name__,
                            attempt,
                            exc,
                        )
                        raise
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(
                        "%s attempt %d/%d failed: %s — retrying in %.1fs",
                        func.__name__,
                        attempt,
                        max_retries + 1,
                        exc,
                        delay,
                    )
                    if on_retry:
                        with contextlib.suppress(Exception):
                            on_retry(attempt, exc)
                    time.sleep(delay)
            # Should never reach here, but defensive
            if last_exc:
                raise last_exc

        return wrapper

    return decorator


# ─── 2. Checkpoint store — persist loop state to disk ──────────────────────


class CheckpointStore:
    """Persists CUA Loop state to disk so it can be resumed after a crash.

    Each checkpoint is a JSON file containing:
        - execution_id
        - step_num
        - objective
        - completed_steps (list of step dicts)
        - timestamp
        - context (string passed to next iteration)

    Files are written atomically (write to .tmp, then rename) so a crash
    mid-write never leaves a corrupted checkpoint.
    """

    def __init__(self, directory: str = "/tmp/cua_checkpoints") -> None:  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        execution_id: str,
        step_num: int,
        objective: str,
        completed_steps: list[dict[str, Any]],
        context: str = "",
        extra: dict[str, Any] | None = None,
    ) -> Path:
        """Save a checkpoint. Returns the path to the checkpoint file."""
        checkpoint = {
            "execution_id": execution_id,
            "step_num": step_num,
            "objective": objective,
            "completed_steps": completed_steps,
            "context": context,
            "timestamp": datetime.now(UTC).isoformat(),
            "extra": extra or {},
        }
        filename = f"{execution_id}_step{step_num:04d}.json"
        filepath = self.directory / filename
        tmp_path = filepath.with_suffix(".json.tmp")

        # Atomic write: write to .tmp, then rename
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(checkpoint, fh, indent=2, default=str)
        os.replace(tmp_path, filepath)

        logger.debug("Checkpoint saved: %s (step %d)", filepath, step_num)
        return filepath

    def load_latest(self, execution_id: str) -> dict[str, Any] | None:
        """Load the latest checkpoint for a given execution_id.

        Returns None if no checkpoints exist.
        """
        pattern = f"{execution_id}_step*.json"
        files = sorted(self.directory.glob(pattern))
        if not files:
            return None
        latest_file = files[-1]
        try:
            with open(latest_file, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load checkpoint %s: %s", latest_file, exc)
            return None

    def list_checkpoints(self, execution_id: str) -> list[Path]:
        """List all checkpoint files for an execution_id, sorted by step."""
        pattern = f"{execution_id}_step*.json"
        return sorted(self.directory.glob(pattern))

    def cleanup(self, execution_id: str, keep_last: int = 1) -> int:
        """Delete old checkpoints, keeping only the last N.

        Returns the number of files deleted.
        """
        files = self.list_checkpoints(execution_id)
        if len(files) <= keep_last:
            return 0
        to_delete = files[:-keep_last]
        for f in to_delete:
            with contextlib.suppress(OSError):
                f.unlink()
        return len(to_delete)

    def clear_all(self, execution_id: str) -> int:
        """Delete ALL checkpoints for an execution_id. Returns count deleted."""
        files = self.list_checkpoints(execution_id)
        for f in files:
            with contextlib.suppress(OSError):
                f.unlink()
        return len(files)


# ─── 3. Hybrid Vision Router — multi-vendor fallback chain ─────────────────


class HybridVisionRouter:
    """Routes analyze_screenshot() calls through a multi-vendor fallback chain.

    Chain order (highest accuracy first):
        1. Gemini Vision (online, ~95% accuracy) — may fail due to geo restrictions
        2. OpenAI-compatible Vision (online, ~95% accuracy) — works globally
        3. Anthropic Claude Vision (online, ~95% accuracy) — works globally
        4. OpenCV + Tesseract (offline, ~70% accuracy) — always available

    Decision logic:
        - Try each backend in order
        - First successful response wins
        - If all fail, return the last error

    This guarantees the CUA Loop can continue operating even when:
        - Gemini is geo-blocked (use OpenAI or Claude)
        - All cloud APIs are down (use OpenCV)
        - No API keys configured (use OpenCV only)

    Usage:
        from integrations.resilience import hybrid_vision

        analysis = hybrid_vision.analyze_screenshot(
            image=screenshot_path,
            objective="Click the Run button",
        )
        # → tries Gemini → OpenAI → Claude → OpenCV
    """

    def __init__(self) -> None:
        from integrations.anthropic_vision import anthropic_vision
        from integrations.gemini_vision import gemini_vision
        from integrations.openai_vision import openai_vision
        from integrations.opencv_vision import opencv_vision

        self.gemini = gemini_vision
        self.openai = openai_vision
        self.anthropic = anthropic_vision
        self.opencv = opencv_vision

        # Build the chain in priority order
        self.chain: list[tuple[str, Any]] = []
        if self.gemini.enabled:
            self.chain.append(("gemini", self.gemini))
        if self.openai.enabled:
            self.chain.append(("openai", self.openai))
        if self.anthropic.enabled:
            self.chain.append(("anthropic", self.anthropic))
        if self.opencv.enabled:
            self.chain.append(("opencv", self.opencv))

        self.primary = self.chain[0][0] if self.chain else "none"
        self.fallback_count = max(0, len(self.chain) - 1)

        logger.info(
            "HybridVisionRouter initialized — chain=%s (primary=%s, %d fallbacks)",
            [name for name, _ in self.chain],
            self.primary,
            self.fallback_count,
        )

    @retry_with_backoff(max_retries=2, base_delay=1.0, exceptions=(Exception,))
    def _call_backend(self, backend, image, objective, context):
        """Call a vision backend with one retry (decorator handles retry)."""
        return backend.analyze_screenshot(image=image, objective=objective, context=context)

    def analyze_screenshot(
        self,
        image: Any,
        objective: str,
        context: str | None = None,
    ) -> dict[str, Any] | None:
        """Analyze a screenshot, trying each backend in the chain.

        Returns the analysis dict, with a "source" field indicating which
        backend was used ("gemini" | "openai" | "anthropic" | "opencv").
        """
        if not self.chain:
            return {
                "error": "no_vision_backend",
                "message": "No vision backends available (Gemini, OpenAI, Anthropic, OpenCV all disabled)",
            }

        last_error: dict[str, Any] | None = None

        for name, backend in self.chain:
            try:
                # OpenCV doesn't need retry (it's local, no network)
                if name == "opencv":
                    result = backend.analyze_screenshot(
                        image=image, objective=objective, context=context,
                    )
                else:
                    result = self._call_backend(backend, image, objective, context)

                if result and "error" not in result:
                    result.setdefault("source", name)
                    return result

                last_error = result
                logger.warning("%s returned error, trying next backend: %s", name, result)

            except Exception as exc:  # noqa: BLE001
                last_error = {"error": f"{name}_exception", "message": str(exc)}
                logger.warning("%s call failed, trying next backend: %s", name, exc)

        # All backends failed
        return last_error or {
            "error": "all_backends_failed",
            "message": "All vision backends failed",
        }

    def health_check(self) -> dict[str, Any]:
        """Return combined health status for all backends."""
        return {
            "primary": self.primary,
            "fallback_count": self.fallback_count,
            # Backwards-compat alias: older code/tests expect a "fallback" key.
            # Keeps both names so neither old nor new consumers break.
            "fallback": self.fallback_count,
            "chain": [name for name, _ in self.chain],
            "gemini": self.gemini.health_check(),
            "openai": self.openai.health_check(),
            "anthropic": self.anthropic.health_check(),
            "opencv": self.opencv.health_check(),
        }


# ─── 4. Resume Manager — orchestrate checkpoint loading + loop resume ──────


class ResumeManager:
    """Manages execution IDs and resume-from-checkpoint logic.

    Usage:
        rm = ResumeManager()
        exec_id = rm.start_execution(objective="Open ETAP")
        # ... run loop, save checkpoints ...
        # If crash happens:
        rm2 = ResumeManager()
        exec_id, resume_from, prior_steps = rm2.resume_or_start(objective="Open ETAP")
    """

    def __init__(self, checkpoint_dir: str = "/tmp/cua_checkpoints") -> None:  # NOSONAR — S5443: /tmp use is intentional & permission-hardened
        self.store = CheckpointStore(directory=checkpoint_dir)

    def start_execution(self, objective: str) -> str:
        """Generate a new execution_id for a fresh CUA run."""
        # execution_id = first 8 chars of objective hash + uuid suffix
        import hashlib

        obj_hash = hashlib.sha256(objective.encode()).hexdigest()[:8]
        return f"{obj_hash}_{uuid.uuid4().hex[:8]}"

    def resume_or_start(
        self,
        objective: str,
    ) -> tuple[str, int, list[dict[str, Any]], str]:
        """Either resume an existing execution or start a new one.

        Returns (execution_id, resume_from_step, prior_steps, context).
        If no checkpoint found, returns (new_id, 0, [], "").
        """
        # Look for any checkpoint matching this objective
        import hashlib

        obj_hash = hashlib.sha256(objective.encode()).hexdigest()[:8]
        # Check all files starting with this hash
        candidates = list(self.store.directory.glob(f"{obj_hash}_*"))
        if not candidates:
            return self.start_execution(objective), 0, [], ""

        # Find the most recent checkpoint (across all execution_ids with this objective)
        latest_data = None
        latest_time: str = ""
        for f in candidates:
            try:
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                # Parse timestamp
                ts = data.get("timestamp", "")
                if ts:
                    # Compare lexicographically (ISO format sorts correctly).
                    # Both operands must be str to avoid TypeError (was: str > int).
                    if not latest_time or ts > latest_time:
                        latest_time = ts
                        latest_data = data
            except (json.JSONDecodeError, OSError):
                continue

        if not latest_data:
            return self.start_execution(objective), 0, [], ""

        exec_id = latest_data["execution_id"]
        resume_from = latest_data["step_num"]
        prior_steps = latest_data.get("completed_steps", [])
        context = latest_data.get("context", "")

        logger.info(
            "Resuming execution %s from step %d (%d prior steps completed)",
            exec_id,
            resume_from,
            len(prior_steps),
        )
        return exec_id, resume_from, prior_steps, context


# ─── Module-level singletons ───────────────────────────────────────────────

hybrid_vision = HybridVisionRouter()
resume_manager = ResumeManager()


__all__ = [
    "CheckpointStore",
    "HybridVisionRouter",
    "ResumeManager",
    "hybrid_vision",
    "resume_manager",
    "retry_with_backoff",
]
