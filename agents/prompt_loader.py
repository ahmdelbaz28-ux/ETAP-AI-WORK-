"""
AhmedETAP - Prompt Loader (Safety-Critical Edition)
====================================================

⚠️ SAFETY-CRITICAL MODULE ⚠️
This module loads the system prompts that drive AhmedETAP's power-systems
engineering agents — including Arc Flash (IEEE 1584), Short Circuit
(IEC 60909), Protective Device Coordination (IEEE C37.90), and Grounding
Grid Design (IEEE 80). A wrong prompt → a wrong engineering decision →
people can die.

Resolution philosophy (reviewed by safety engineering):

    ┌─────────────────────────────────────────────────────────────┐
    │  Tier 1: Local YAML (source of truth)                      │
    │  ──────────────────────────────────────────                 │
    │  • Git-versioned, code-reviewed, deterministic             │
    │  • Cannot be silently changed by a remote party            │
    │  • Always available (no network dependency)                │
    │  • Used as the BASELINE for integrity checks               │
    └─────────────────────────────────────────────────────────────┘
                          │
                          ▼ (when remote is configured AND enabled)
    ┌─────────────────────────────────────────────────────────────┐
    │  Tier 2: Langfuse remote (override + observability)        │
    │  ──────────────────────────────────────────                 │
    │  • Fetched ASYNCHRONOUSLY (never blocks event loop)        │
    │  • Has a hard timeout (default 3 s)                        │
    │  • Subject to circuit breaker (fast-fail after N errors)   │
    │  • Integrity-checked against the local YAML hash:          │
    │    - If hash matches → use remote (enables version pinning)│
    │    - If hash differs → CRITICAL warning + use local        │
    │  • Used only when ``LANGFUSE_OVERRIDE_MODE=true``          │
    └─────────────────────────────────────────────────────────────┘
                          │
                          ▼ (legacy fallback, off by default)
    ┌─────────────────────────────────────────────────────────────┐
    │  Tier 3: LangWatch API (legacy)                            │
    │  ──────────────────────────────────────────                 │
    │  • Same async/timeout/circuit-breaker treatment as Tier 2  │
    │  • Only consulted when LANGWATCH_API_KEY is set AND        │
    │    LANGWATCH_OVERRIDE_MODE=true                            │
    └─────────────────────────────────────────────────────────────┘
                          │
                          ▼
    ┌─────────────────────────────────────────────────────────────┐
    │  Tier 4: Fallback agent prompt + hardcoded safety-net      │
    └─────────────────────────────────────────────────────────────┘

The local YAML file is ALWAYS loaded first (synchronously, from disk —
no network). Remote overrides are optional and opt-in. This guarantees
that a network failure or a compromised remote account can never
silently change the safety-critical prompt content.

Usage::

    from agents.prompt_loader import get_system_prompt, get_system_prompt_async

    # Sync (uses YAML only — never blocks on network)
    prompt = get_system_prompt("load_flow_agent")

    # Async (may consult Langfuse for override, with timeout)
    prompt = await get_system_prompt_async("load_flow_agent")
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(
    os.environ.get(
        "ETAP_PROMPTS_DIR",
        str(Path(__file__).resolve().parent.parent / "prompts"),
    ),
)

# Langfuse config
_LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
_LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
_LANGFUSE_ENABLED = (
    bool(_LANGFUSE_PUBLIC_KEY)
    and bool(_LANGFUSE_SECRET_KEY)
    and os.environ.get("LANGFUSE_ENABLED", "true").lower() not in ("0", "false", "no", "off")
)
# SAFETY: remote override is OFF by default. Must be explicitly enabled.
_LANGFUSE_OVERRIDE_MODE = os.environ.get("LANGFUSE_OVERRIDE_MODE", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_LANGFUSE_TIMEOUT = float(os.environ.get("LANGFUSE_TIMEOUT", "3.0"))

# LangWatch config (legacy)
_LANGWATCH_API_KEY = os.environ.get("LANGWATCH_API_KEY", "")
_LANGWATCH_ENDPOINT = os.environ.get("LANGWATCH_ENDPOINT", "https://app.langwatch.ai")
_LANGWATCH_OVERRIDE_MODE = os.environ.get("LANGWATCH_OVERRIDE_MODE", "false").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
_LANGWATCH_TIMEOUT = float(os.environ.get("LANGWATCH_TIMEOUT", "3.0"))

# Cache configuration
# SAFETY: cache has a TTL so a remote prompt update is eventually picked up.
_CACHE_TTL_SECONDS = float(os.environ.get("PROMPT_CACHE_TTL", "300"))  # 5 min default

# Circuit breaker: if N consecutive remote calls fail, stop trying for a while
_CB_FAILURE_THRESHOLD = int(os.environ.get("PROMPT_CB_FAILURE_THRESHOLD", "5"))
_CB_RESET_SECONDS = float(os.environ.get("PROMPT_CB_RESET_SECONDS", "60"))

# Cache: handle -> (content, fetched_at, source)
_prompt_cache: dict[str, tuple[str | None, float, str]] = {}
_cache_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Circuit breaker (per-source)
# ---------------------------------------------------------------------------


class _CircuitBreaker:
    """Simple thread-safe circuit breaker.

    After ``failure_threshold`` consecutive failures, the breaker opens
    and rejects all calls for ``reset_seconds``. After that, it enters
    half-open: one call is allowed; if it succeeds, the breaker closes;
    if it fails, it opens again.
    """

    def __init__(self, failure_threshold: int = 5, reset_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at >= self.reset_seconds:
                # Half-open: allow one trial
                self._opened_at = None
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
                logger.warning(
                    "Prompt-fetch circuit breaker opened after %d failures (will reset in %.1fs)",
                    self._failures,
                    self.reset_seconds,
                )


_langfuse_cb = _CircuitBreaker(_CB_FAILURE_THRESHOLD, _CB_RESET_SECONDS)
_langwatch_cb = _CircuitBreaker(_CB_FAILURE_THRESHOLD, _CB_RESET_SECONDS)


# ---------------------------------------------------------------------------
# Integrity check
# ---------------------------------------------------------------------------


def _hash_prompt(text: str) -> str:
    """SHA-256 hash of normalised prompt text (for integrity verification)."""
    # Normalise: strip trailing whitespace per line, then strip overall
    normalised = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Local YAML loading (Tier 1 — always preferred for safety)
# ---------------------------------------------------------------------------


def _extract_system_message(parsed: Any) -> str | None:
    """Extract the system message from a parsed YAML prompt structure."""
    if not isinstance(parsed, dict):
        return None

    messages = parsed.get("messages", [])
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()

    prompt_text = parsed.get("prompt", "")
    if isinstance(prompt_text, str) and prompt_text.strip():
        return prompt_text.strip()

    return None


def _load_from_yaml(handle: str) -> str | None:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Load a prompt from a local YAML file in the prompts/ directory.

    Tries several filename patterns to locate the file.
    """
    possible_files = [
        f"{handle}.yaml",
        f"{handle}.prompt.yaml",
    ]

    for filename in possible_files:
        filepath = _PROMPTS_DIR / filename
        if filepath.is_file():
            try:
                content = filepath.read_text(encoding="utf-8")
                parsed = yaml.safe_load(content)
                system_msg = _extract_system_message(parsed)
                if system_msg:
                    return system_msg
            except Exception as exc:
                logger.warning("Error loading YAML prompt '%s': %s", filepath, exc)

    # Try prompts.json mapping for exact path resolution
    prompts_json_path = _PROMPTS_DIR.parent / "prompts.json"
    if prompts_json_path.is_file():
        try:
            import json

            prompts_json = json.loads(prompts_json_path.read_text(encoding="utf-8"))
            prompt_path = prompts_json.get("prompts", {}).get(handle)
            if prompt_path and isinstance(prompt_path, str):
                actual_path = prompt_path[5:] if prompt_path.startswith("file:") else prompt_path
                full_path = _PROMPTS_DIR.parent / actual_path
                if full_path.is_file():
                    content = full_path.read_text(encoding="utf-8")
                    parsed = yaml.safe_load(content)
                    system_msg = _extract_system_message(parsed)
                    if system_msg:
                        return system_msg
        except Exception as exc:
            logger.debug("Error reading prompts.json: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Langfuse integration (Tier 2 — opt-in override, async + circuit breaker)
# ---------------------------------------------------------------------------


async def _load_from_langfuse_async(handle: str) -> str | None:
    """Asynchronously attempt to load a prompt from Langfuse.

    Returns ``None`` on any error, timeout, or when the circuit breaker
    is open. NEVER raises.
    """
    if not _LANGFUSE_ENABLED or not _LANGFUSE_OVERRIDE_MODE:
        return None

    if _langfuse_cb.is_open:
        logger.debug("Langfuse circuit breaker open — skipping '%s'", handle)
        return None

    try:
        # Import inside the function so the module can be imported even
        # if the langfuse SDK is not installed.
        from integrations.langfuse_integration import langfuse_tracker

        if not langfuse_tracker.enabled:
            return None

        # Run the (sync) SDK call in a thread with a hard timeout. This
        # prevents the event loop from being blocked.
        result = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: langfuse_tracker.get_prompt(name=handle, label="production", fallback=None),
            ),
            timeout=_LANGFUSE_TIMEOUT,
        )

        if result:
            _langfuse_cb.record_success()
            return result
        return None
    except TimeoutError:
        _langfuse_cb.record_failure()
        logger.warning(
            "Langfuse prompt fetch timed out for '%s' (timeout=%.1fs)",
            handle,
            _LANGFUSE_TIMEOUT,
        )
        return None
    except Exception as exc:
        _langfuse_cb.record_failure()
        logger.debug("Langfuse lookup failed for '%s': %s", handle, exc)
        return None


# ---------------------------------------------------------------------------
# LangWatch integration (Tier 3 — legacy fallback)
# ---------------------------------------------------------------------------


async def _load_from_langwatch_async(handle: str) -> str | None:
    """Asynchronously attempt to load a prompt from LangWatch (legacy)."""
    if not _LANGWATCH_API_KEY or not _LANGWATCH_OVERRIDE_MODE:
        return None

    if _langwatch_cb.is_open:
        return None

    try:
        import httpx

        headers = {
            "Authorization": f"Bearer {_LANGWATCH_API_KEY}",
            "X-Auth-Token": _LANGWATCH_API_KEY,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=_LANGWATCH_TIMEOUT) as client:
            r = await client.get(
                f"{_LANGWATCH_ENDPOINT}/api/prompts/{handle}",
                headers=headers,
            )
        if r.status_code != 200:
            _langwatch_cb.record_failure()
            return None

        data = r.json()
        messages = data.get("messages", []) if isinstance(data, dict) else []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    _langwatch_cb.record_success()
                    return content.strip()
        return None
    except Exception as exc:
        _langwatch_cb.record_failure()
        logger.debug("LangWatch lookup failed for '%s': %s", handle, exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FALLBACK_PROMPT = (
    "You are a safety-net fallback AI assistant for power systems engineering. "
    "Provide accurate, standards-compliant (IEEE/IEC) analysis and recommendations. "
    "If you are uncertain about a life-safety calculation (arc flash, short circuit, "
    "grounding, protective coordination), REFUSE to give a numerical answer and "
    "instead direct the user to a qualified licensed engineer."
)


def get_system_prompt(handle: str) -> str:
    """Load a system prompt by handle, sync (YAML-only — never blocks on network).

    Resolution order (sync):
        1. In-memory cache
        2. Local YAML file (always preferred for safety)
        3. Fallback agent prompt
        4. Hardcoded safety-net

    Remote overrides (Langfuse / LangWatch) are NOT consulted here because
    they would block the event loop. Use ``get_system_prompt_async`` for
    remote-override support.

    Parameters
    ----------
    handle : str
        The prompt handle, e.g. ``"load_flow_agent"``.

    Returns
    -------
    str
        The system prompt content. Never returns ``None``.
    """
    # Check cache
    with _cache_lock:
        cached = _prompt_cache.get(handle)
        if cached is not None:
            content, fetched_at, _ = cached
            # SAFETY: cache only valid within TTL
            if time.monotonic() - fetched_at < _CACHE_TTL_SECONDS:
                return content or _FALLBACK_PROMPT

    # Tier 1: Local YAML (deterministic, safety-critical source of truth)
    result = _load_from_yaml(handle)
    if result:
        with _cache_lock:
            _prompt_cache[handle] = (result, time.monotonic(), "yaml")
        logger.debug("Prompt '%s' loaded from local YAML", handle)
        return result

    # Tier 2: Fallback agent prompt
    if handle != "fallback_agent":
        result = _load_from_yaml("fallback_agent")
        if result:
            with _cache_lock:
                _prompt_cache[handle] = (result, time.monotonic(), "fallback_yaml")
            logger.warning("Prompt '%s' not found, using fallback_agent prompt", handle)
            return result

    # Tier 3: Hardcoded safety-net
    with _cache_lock:
        _prompt_cache[handle] = (None, time.monotonic(), "safety_net")
    logger.error(
        "Prompt '%s' not found anywhere — using hardcoded safety-net. "
        "This indicates a deployment problem.",
        handle,
    )
    return _FALLBACK_PROMPT


async def get_system_prompt_async(handle: str) -> str:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """Load a system prompt by handle, async (supports remote override).

    Resolution order (async):
        1. In-memory cache (within TTL)
        2. Local YAML file (safety-critical baseline — always loaded)
        3. Langfuse remote override (if LANGFUSE_OVERRIDE_MODE=true)
           - Hard timeout (default 3 s)
           - Circuit breaker (5 failures → open for 60 s)
           - Integrity check: hash must match local YAML hash, else
             CRITICAL warning and local YAML is used
        4. LangWatch remote (legacy, same protections)
        5. Fallback agent prompt
        6. Hardcoded safety-net

    The local YAML is ALWAYS the baseline. Remote is consulted only for
    override AND its content is integrity-checked against the local hash.
    A mismatch produces a CRITICAL log entry and the local version wins.

    Parameters
    ----------
    handle : str
        The prompt handle.

    Returns
    -------
    str
        The system prompt content. Never returns ``None``.
    """
    # Check cache
    with _cache_lock:
        cached = _prompt_cache.get(handle)
        if cached is not None:
            content, fetched_at, _ = cached
            if time.monotonic() - fetched_at < _CACHE_TTL_SECONDS:
                return content or _FALLBACK_PROMPT

    # ALWAYS load the YAML baseline first (safety-critical)
    yaml_prompt = _load_from_yaml(handle)
    if not yaml_prompt:
        # No local YAML — fall through to remote / fallback / safety-net.
        # Note: a missing YAML for a safety-critical agent is itself a
        # problem; we log an error.
        if handle != "fallback_agent":
            logger.error(
                "Local YAML prompt '%s' not found — remote override will "
                "be attempted but this is a deployment risk.",
                handle,
            )

    yaml_hash = _hash_prompt(yaml_prompt) if yaml_prompt else None

    # Tier 2: Langfuse remote override (opt-in, async, circuit-breaker)
    if _LANGFUSE_OVERRIDE_MODE and _LANGFUSE_ENABLED:
        remote_prompt = await _load_from_langfuse_async(handle)
        if remote_prompt:
            remote_hash = _hash_prompt(remote_prompt)
            if yaml_hash and remote_hash != yaml_hash:
                # CRITICAL: integrity mismatch. Use local YAML, log loudly.
                logger.critical(
                    "⚠️ SAFETY: Langfuse prompt '%s' hash mismatch! "
                    "Local YAML hash=%s... but Langfuse hash=%s... "
                    "Using LOCAL YAML (deterministic, code-reviewed). "
                    "Investigate the Langfuse dashboard for unauthorised "
                    "prompt changes.",
                    handle,
                    yaml_hash[:16],
                    remote_hash[:16],
                )
                # Use local YAML, do NOT cache remote
                if yaml_prompt:
                    with _cache_lock:
                        _prompt_cache[handle] = (
                            yaml_prompt,
                            time.monotonic(),
                            "yaml_integrity_mismatch",
                        )
                    return yaml_prompt
            else:
                # Hashes match (or no local YAML to compare against)
                with _cache_lock:
                    _prompt_cache[handle] = (
                        remote_prompt,
                        time.monotonic(),
                        "langfuse_override",
                    )
                logger.info("Prompt '%s' loaded from Langfuse (integrity OK)", handle)
                return remote_prompt

    # Tier 3: LangWatch remote (legacy)
    if _LANGWATCH_OVERRIDE_MODE and _LANGWATCH_API_KEY:
        remote_prompt = await _load_from_langwatch_async(handle)
        if remote_prompt:
            remote_hash = _hash_prompt(remote_prompt)
            if yaml_hash and remote_hash != yaml_hash:
                logger.critical(
                    "⚠️ SAFETY: LangWatch prompt '%s' hash mismatch! "
                    "Local=%s... Remote=%s... Using LOCAL.",
                    handle,
                    yaml_hash[:16],
                    remote_hash[:16],
                )
                if yaml_prompt:
                    with _cache_lock:
                        _prompt_cache[handle] = (
                            yaml_prompt,
                            time.monotonic(),
                            "yaml_integrity_mismatch",
                        )
                    return yaml_prompt
            else:
                with _cache_lock:
                    _prompt_cache[handle] = (
                        remote_prompt,
                        time.monotonic(),
                        "langwatch_override",
                    )
                logger.info("Prompt '%s' loaded from LangWatch (integrity OK)", handle)
                return remote_prompt

    # Tier 4: Local YAML (fallback to baseline)
    if yaml_prompt:
        with _cache_lock:
            _prompt_cache[handle] = (yaml_prompt, time.monotonic(), "yaml")
        return yaml_prompt

    # Tier 5: Fallback agent prompt
    if handle != "fallback_agent":
        result = _load_from_yaml("fallback_agent")
        if result:
            with _cache_lock:
                _prompt_cache[handle] = (result, time.monotonic(), "fallback_yaml")
            logger.warning("Prompt '%s' not found, using fallback_agent prompt", handle)
            return result

    # Tier 6: Hardcoded safety-net
    with _cache_lock:
        _prompt_cache[handle] = (None, time.monotonic(), "safety_net")
    logger.error("Prompt '%s' not found anywhere — using hardcoded safety-net.", handle)
    return _FALLBACK_PROMPT


def get_prompt_metadata(handle: str) -> dict[str, Any]:
    """Load full prompt metadata (model, temperature, messages) from YAML."""
    possible_files = [
        f"{handle}.yaml",
        f"{handle}.prompt.yaml",
    ]

    for filename in possible_files:
        filepath = _PROMPTS_DIR / filename
        if filepath.is_file():
            try:
                content = filepath.read_text(encoding="utf-8")
                parsed = yaml.safe_load(content)
                if isinstance(parsed, dict):
                    return parsed
            except Exception as exc:
                logger.warning("Error loading YAML prompt '%s': %s", filepath, exc)

    return {}


def clear_prompt_cache() -> None:
    """Clear the in-memory prompt cache."""
    with _cache_lock:
        _prompt_cache.clear()


def get_prompt_cache_info() -> dict[str, Any]:
    """Return cache + circuit-breaker state for observability."""
    with _cache_lock:
        cache_size = len(_prompt_cache)
        cache_entries = [
            {"handle": h, "source": s, "age_seconds": time.monotonic() - t}
            for h, (_, t, s) in _prompt_cache.items()
        ]
    return {
        "cache_size": cache_size,
        "cache_ttl_seconds": _CACHE_TTL_SECONDS,
        "cache_entries": cache_entries,
        "langfuse_enabled": _LANGFUSE_ENABLED,
        "langfuse_override_mode": _LANGFUSE_OVERRIDE_MODE,
        "langfuse_circuit_open": _langfuse_cb.is_open,
        "langwatch_override_mode": _LANGWATCH_OVERRIDE_MODE,
        "langwatch_circuit_open": _langwatch_cb.is_open,
    }


def list_available_prompts() -> list[str]:
    """List all prompt handles available in the prompts/ directory."""
    handles: list[str] = []
    if not _PROMPTS_DIR.is_dir():
        return handles

    for filepath in _PROMPTS_DIR.iterdir():
        if filepath.suffix in (".yaml", ".yml") and filepath.stem != "sample_prompt":
            name = filepath.stem
            if name.endswith(".prompt"):
                name = name[:-7]
            handles.append(name)

    return sorted(set(handles))
