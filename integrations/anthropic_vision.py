"""
integrations/anthropic_vision.py — Anthropic Claude Vision API integration

Provides visual perception via Anthropic's Claude API (claude-3.5-sonnet,
claude-3-opus, etc.). Used as a fallback in the multi-vendor chain when
Gemini and OpenAI are unavailable.

WHY THIS EXISTS:
    Google Gemini has geographic restrictions. OpenAI requires a different
    key. Claude Vision provides a third option with global availability
    and excellent vision capabilities.

SUPPORTED MODELS:
  - claude-3-5-sonnet-20241022 (latest, recommended)
  - claude-3-opus-20240229
  - claude-3-sonnet-20240229
  - claude-3-haiku-20240307 (fastest, cheapest)

CONFIGURATION (env vars):
    ANTHROPIC_API_KEY      — API key (required)
    ANTHROPIC_VISION_MODEL — Model name (default: claude-3-5-sonnet-20241022)
    ANTHROPIC_TIMEOUT      — Per-request timeout in seconds (default: 30)
    ANTHROPIC_MAX_RETRIES  — Max retries on transient errors (default: 3)
    ANTHROPIC_BASE_URL     — Base URL (default: https://api.anthropic.com)

USAGE:
    from integrations.anthropic_vision import anthropic_vision

    analysis = anthropic_vision.analyze_screenshot(
        image_path="/tmp/screenshot.png",
        objective="Click the Run button",
    )

References:
    - integrations/gemini_vision.py (sibling — Gemini backend)
    - integrations/openai_vision.py (sibling — OpenAI backend)
    - integrations/resilience.py (HybridVisionRouter consumer)
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Optional deps ─────────────────────────────────────────────────────────

try:
    import httpx  # noqa: F401 — used in _make_request_httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ─── Constants ─────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0
ANTHROPIC_VERSION = "2023-06-01"

# System prompt — same contract as Gemini/OpenAI (structured JSON output)
SYSTEM_PROMPT = """You are the Visual Perception Layer of the ETAP GUI Agent, a Computer Use Agent
that operates engineering desktop applications (ETAP, Revit, AutoCAD, SCADA, QGIS, ArcGIS)
and web applications.

Given a screenshot and an objective, you must:
1. Describe what you see on the screen (windows, dialogs, menus, buttons, text, status bars).
2. Identify clickable UI elements with their approximate pixel coordinates (x, y).
   Use the top-left corner of the screenshot as (0, 0).
3. Recommend the NEXT single action that moves toward the objective.
   - If a button needs to be clicked: {"type": "click", "x": <int>, "y": <int>, "target": "<name>"}
   - If text needs to be typed:       {"type": "type", "text": "<string>", "x": <int>, "y": <int>}
   - If a hotkey needs to be pressed: {"type": "hotkey", "keys": ["ctrl", "s"]}
   - If we should wait:               {"type": "wait", "seconds": <float>}
   - If the objective is complete:    {"type": "done", "summary": "<result>"}
   - If you cannot determine action:  {"type": "unknown", "reason": "<string>"}

CRITICAL SAFETY RULES:
- NEVER recommend clicking OK/Yes on confirmation dialogs that mention "Delete", "Format",
  "Override", or "Reset" — return {"type": "unknown", "reason": "destructive dialog requires human"}.
- If you see an error dialog, return {"type": "unknown", "reason": "error dialog: <text>"}.
- Coordinates must be integers within the screenshot bounds.
- Be conservative: if uncertain, return "unknown" rather than guessing.

You MUST respond with valid JSON only (no markdown, no prose). The JSON schema:
{
  "description": "<one-paragraph summary of the screen>",
  "ui_elements": [
    {"type": "button|menu|input|dialog|text|icon", "label": "<text>", "x": <int>, "y": <int>, "confidence": <0.0-1.0>}
  ],
  "next_action": {
    "type": "click|type|hotkey|wait|done|unknown",
    "x": <int>,
    "y": <int>,
    "text": "<string, only for type>",
    "keys": ["<key1>", "<key2>"],
    "target": "<element name>",
    "seconds": <float>,
    "summary": "<result, only for done>",
    "reason": "<string, only for unknown>"
  },
  "objective_complete": <bool>,
  "confidence": <0.0-1.0>
}
"""


# ─── Anthropic Vision Client ───────────────────────────────────────────────


class AnthropicVisionClient:
    """Anthropic Claude Vision API client.

    Graceful degradation:
        - No API key → enabled=False, all calls return None
        - httpx missing → falls back to urllib
        - API error → returns error dict, never raises
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = os.getenv("ANTHROPIC_VISION_MODEL", DEFAULT_MODEL)
        self.timeout = int(os.getenv("ANTHROPIC_TIMEOUT", str(DEFAULT_TIMEOUT)))
        self.max_retries = int(os.getenv("ANTHROPIC_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))

        self.enabled = bool(self.api_key and PIL_AVAILABLE)

        if self.enabled:
            logger.info(
                "✅ Anthropic Vision initialized — model: %s, base_url: %s, timeout: %ds",
                self.model,
                self.base_url,
                self.timeout,
            )
        else:
            missing: List[str] = []
            if not self.api_key:
                missing.append("ANTHROPIC_API_KEY")
            if not PIL_AVAILABLE:
                missing.append("pillow")
            logger.info("Anthropic Vision disabled — missing: %s", ", ".join(missing))

    # ─── Public API ────────────────────────────────────────────────────────

    def analyze_screenshot(
        self,
        image: Any,
        objective: str,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze a screenshot using Anthropic Claude Vision API."""
        if not self.enabled:
            return None

        pil_image = self._to_pil_image(image)
        if pil_image is None:
            return {"error": "invalid_image", "message": "Could not convert input to PIL Image"}

        # Encode image as base64
        image_b64 = self._image_to_base64(pil_image)
        if not image_b64:
            return {"error": "image_encoding_failed", "message": "Could not encode image to base64"}

        # Build the messages (Anthropic format)
        width, height = pil_image.size
        user_text = (
            f"OBJECTIVE: {objective}\n"
            f"SCREENSHOT_SIZE: {width}x{height} pixels\n"
            + (f"PRIOR_CONTEXT: {context}\n" if context else "")
            + "Analyze the screenshot and respond with the JSON object described "
            "in the system instructions. Remember: coordinates must be integers "
            "within the screenshot bounds, and you MUST return valid JSON only."
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_text},
                ],
            }
        ]

        # Build request payload (Anthropic format)
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "temperature": 0.1,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }

        # Build headers (Anthropic-specific)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

        url = f"{self.base_url}/v1/messages"

        # Retry loop
        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._make_request(url, headers, payload)
                return self._parse_response(response)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Anthropic Vision attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    last_error,
                )
                if attempt < self.max_retries:
                    time.sleep(RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1)))

        return {
            "error": "api_error",
            "message": f"All {self.max_retries} attempts failed. Last: {last_error}",
        }

    def health_check(self) -> Dict[str, Any]:
        """Return client status for /health endpoints."""
        return {
            "enabled": self.enabled,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_set": bool(self.api_key),
            "pil_available": PIL_AVAILABLE,
            "httpx_available": HTTPX_AVAILABLE,
            "timeout_seconds": self.timeout,
            "max_retries": self.max_retries,
        }

    # ─── Internal helpers ──────────────────────────────────────────────────

    @staticmethod
    def _to_pil_image(image: Any):
        """Coerce various image inputs into a PIL.Image.Image."""
        if not PIL_AVAILABLE:
            return None
        try:
            if isinstance(image, Image.Image):
                return image
            if isinstance(image, (bytes, bytearray)):
                return Image.open(io.BytesIO(image))
            if isinstance(image, (str, Path)):
                return Image.open(image)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to convert image: %s", exc)
        return None

    @staticmethod
    def _image_to_base64(pil_image) -> Optional[str]:
        """Convert PIL Image to base64 string (no data URL prefix)."""
        try:
            buffer = io.BytesIO()
            # Resize if too large
            max_dim = 1568
            if pil_image.width > max_dim or pil_image.height > max_dim:
                ratio = max_dim / max(pil_image.width, pil_image.height)
                new_size = (int(pil_image.width * ratio), int(pil_image.height * ratio))
                pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

            pil_image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("ascii")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image encoding failed: %s", exc)
            return None

    def _make_request(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make the HTTP request to the Anthropic endpoint."""
        if HTTPX_AVAILABLE:
            return self._make_request_httpx(url, headers, payload)
        return self._make_request_urllib(url, headers, payload)

    def _make_request_httpx(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make request using httpx."""
        import httpx

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _make_request_urllib(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback: make request using urllib."""
        import urllib.request

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)

    @staticmethod
    def _parse_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the Anthropic Messages API response.

        Expected structure:
        {
            "content": [
                {"type": "text", "text": "{\"description\": ...}"}
            ],
            ...
        }
        """
        try:
            content_blocks = response.get("content", [])
            if not content_blocks:
                return {
                    "error": "no_content",
                    "message": "API returned no content blocks",
                    "raw": str(response)[:500],
                }

            # Find the text block
            text_content = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    text_content += block.get("text", "")

            if not text_content:
                return {
                    "error": "empty_content",
                    "message": "API returned empty text content",
                    "raw": str(response)[:500],
                }

            # Strip markdown code fences if present
            text_content = text_content.strip()
            if text_content.startswith("```"):
                lines = text_content.split("\n")
                text_content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

            parsed = json.loads(text_content)
            parsed["source"] = "anthropic"
            return parsed

        except json.JSONDecodeError as exc:
            return {
                "error": "json_parse_error",
                "message": f"Could not parse content as JSON: {exc}",
                "raw_content": text_content[:500] if "text_content" in dir() else "?",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "error": "parse_error",
                "message": f"{type(exc).__name__}: {exc}",
                "raw": str(response)[:500],
            }


# ─── Module-level singleton ────────────────────────────────────────────────

anthropic_vision = AnthropicVisionClient()


__all__ = ["AnthropicVisionClient", "anthropic_vision"]
