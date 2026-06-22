"""
AhmedETAP - Prompt Loader
================================================

Mirrors the TypeScript ``getSystemPrompt()`` from ``src/mastra/prompts.ts``
on the Python side, providing the same 3-tier fallback:

1. LangWatch API  (if LANGWATCH_API_KEY is set)
2. Local YAML file in ``prompts/``
3. Hardcoded default safety-net

Usage::

    from agents.prompt_loader import get_system_prompt

    prompt = get_system_prompt("load_flow_agent")
    # Returns the system message content from the YAML prompt file.

This module is used by BaseAgent so every Python agent can access its
prompt-driven description, standards references, and execution guidance
without hardcoding any of that information.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(
    os.environ.get("ETAP_PROMPTS_DIR", str(Path(__file__).resolve().parent.parent / "prompts"))
)
_LANGWATCH_API_KEY = os.environ.get("LANGWATCH_API_KEY", "")
_LANGWATCH_ENDPOINT = os.environ.get("LANGWATCH_ENDPOINT", "https://app.langwatch.ai")

# Cache for loaded prompts to avoid redundant I/O
_prompt_cache: Dict[str, str | None] = {}


# ---------------------------------------------------------------------------
# LangWatch integration
# ---------------------------------------------------------------------------

def _load_from_langwatch(handle: str) -> str | None:
    """Attempt to load a prompt from the LangWatch API.

    Returns the system message content if found, ``None`` otherwise.
    Silently returns ``None`` on any error (network, auth, missing prompt).
    """
    if not _LANGWATCH_API_KEY:
        return None

    try:
        import langwatch  # type: ignore

        langwatch.api_key = _LANGWATCH_API_KEY
        prompt_data = langwatch.prompts.get(handle)

        if prompt_data is None:
            return None

        # LangWatch returns either a flat prompt string or a messages list
        if isinstance(prompt_data, dict):
            # Check for flat prompt field
            prompt_text = prompt_data.get("prompt", "")
            if isinstance(prompt_text, str) and prompt_text.strip():
                return prompt_text.strip()

            # Check messages array for system message
            messages = prompt_data.get("messages", [])
            if isinstance(messages, list):
                for msg in messages:
                    if isinstance(msg, dict) and msg.get("role") == "system":
                        content = msg.get("content", "")
                        if isinstance(content, str) and content.strip():
                            return content.strip()
                        # Content might be a list of content parts
                        if isinstance(content, list):
                            parts = []
                            for part in content:
                                if isinstance(part, str):
                                    parts.append(part)
                                elif isinstance(part, dict) and "text" in part:
                                    parts.append(str(part["text"]))
                            combined = "\n".join(parts).strip()
                            if combined:
                                return combined

        elif isinstance(prompt_data, str) and prompt_data.strip():
            return prompt_data.strip()

        return None

    except ImportError:
        logger.debug("langwatch package not installed, skipping API lookup")
        return None
    except Exception as exc:
        logger.debug("LangWatch lookup failed for '%s': %s", handle, exc)
        return None


# ---------------------------------------------------------------------------
# Local YAML loading
# ---------------------------------------------------------------------------

def _extract_system_message(parsed: Any) -> str | None:
    """Extract the system message from a parsed YAML prompt structure."""
    if not isinstance(parsed, dict):
        return None

    # Check messages array
    messages = parsed.get("messages", [])
    if isinstance(messages, list):
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") == "system":
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()

    # Check flat prompt field
    prompt_text = parsed.get("prompt", "")
    if isinstance(prompt_text, str) and prompt_text.strip():
        return prompt_text.strip()

    return None


def _load_from_yaml(handle: str) -> str | None:
    """Load a prompt from a local YAML file in the prompts/ directory.

    Tries several filename patterns to locate the file, matching the
    TypeScript implementation's search logic.
    """
    # Possible filenames to search
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
# Public API
# ---------------------------------------------------------------------------

# Hardcoded safety-net (mirrors the TS fallback)
_FALLBACK_PROMPT = (
    "You are a safety-net fallback AI assistant for power systems engineering. "
    "Provide accurate, standards-compliant (IEEE/IEC) analysis and recommendations."
)


def get_system_prompt(handle: str) -> str:
    """Load a system prompt by handle, with 3-tier fallback.

    Resolution order:
        1. In-memory cache (prevents redundant I/O and API calls)
        2. LangWatch API (if ``LANGWATCH_API_KEY`` is configured)
        3. Local YAML file in ``prompts/``
        4. Fallback agent prompt (``fallback_agent``)
        5. Hardcoded safety-net default

    Parameters
    ----------
    handle : str
        The prompt handle, e.g. ``"load_flow_agent"``.

    Returns
    -------
    str
        The system prompt content.  Never returns ``None``; falls back
        to a generic safety-net string if all lookups fail.
    """
    # Check cache first
    if handle in _prompt_cache:
        return _prompt_cache[handle] or _FALLBACK_PROMPT

    # Tier 1: LangWatch API
    if os.environ.get("DEPLOYMENT_VERIFICATION") != "true":
        result = _load_from_langwatch(handle)
        if result:
            _prompt_cache[handle] = result
            logger.info("Prompt '%s' loaded from LangWatch API", handle)
            return result

    # Tier 2: Local YAML file
    result = _load_from_yaml(handle)
    if result:
        _prompt_cache[handle] = result
        logger.info("Prompt '%s' loaded from local YAML", handle)
        return result

    # Tier 3: Fallback agent prompt
    if handle != "fallback_agent":
        result = _load_from_yaml("fallback_agent")
        if result:
            _prompt_cache[handle] = result
            logger.warning("Prompt '%s' not found, using fallback_agent prompt", handle)
            return result

    # Tier 4: Hardcoded safety-net
    _prompt_cache[handle] = None
    logger.warning("Prompt '%s' not found anywhere, using hardcoded fallback", handle)
    return _FALLBACK_PROMPT


def get_prompt_metadata(handle: str) -> Dict[str, Any]:
    """Load full prompt metadata (model, temperature, messages) from YAML.

    Unlike ``get_system_prompt()`` which returns just the system message,
    this returns the full parsed YAML structure including model name and
    temperature settings.

    Parameters
    ----------
    handle : str
        The prompt handle, e.g. ``"load_flow_agent"``.

    Returns
    -------
    Dict[str, Any]
        Parsed YAML content, or an empty dict if not found.
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
                if isinstance(parsed, dict):
                    return parsed
            except Exception as exc:
                logger.warning("Error loading YAML prompt '%s': %s", filepath, exc)

    return {}


def clear_prompt_cache() -> None:
    """Clear the in-memory prompt cache.

    Useful for testing or when prompts have been updated on disk and
    need to be re-read.
    """
    _prompt_cache.clear()


def list_available_prompts() -> List[str]:
    """List all prompt handles available in the prompts/ directory.

    Returns
    -------
    List[str]
        Sorted list of prompt handles derived from YAML filenames.
    """
    handles: List[str] = []
    if not _PROMPTS_DIR.is_dir():
        return handles

    for filepath in _PROMPTS_DIR.iterdir():
        if filepath.suffix in (".yaml", ".yml") and filepath.stem != "sample_prompt":
            name = filepath.stem
            # Normalize: strip .prompt suffix if present
            if name.endswith(".prompt"):
                name = name[:-7]
            handles.append(name)

    return sorted(set(handles))
