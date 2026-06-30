"""
integrations/openai_vision.py — OpenAI-compatible Vision API integration

Works with ANY OpenAI-compatible endpoint:
  - OpenAI (api.openai.com)
  - Azure OpenAI
  - Together AI
  - Groq
  - LocalAI / vLLM / Ollama with OpenAI-compatible mode
  - Any provider that implements the OpenAI Chat Completions API

WHY THIS EXISTS:
    Google Gemini API has geographic restrictions ("User location is not
    supported"). On HF Space, Gemini calls fail. This module provides an
    alternative vision backend that works in ALL regions.

SUPPORTED MODELS:
  - gpt-4o, gpt-4o-mini, gpt-4-turbo (OpenAI)
  - gpt-4-vision-preview (legacy)
  - Any model that accepts image_url in messages

CONFIGURATION (env vars):
    OPENAI_API_KEY       — API key (required)
    OPENAI_BASE_URL      — Base URL (default: https://api.openai.com/v1)
                           For Azure: https://your-resource.openai.azure.com/openai/deployments/your-deployment
    OPENAI_VISION_MODEL  — Model name (default: gpt-4o)
    OPENAI_TIMEOUT       — Per-request timeout in seconds (default: 30)
    OPENAI_MAX_RETRIES   — Max retries on transient errors (default: 3)

USAGE:
    from integrations.openai_vision import openai_vision

    analysis = openai_vision.analyze_screenshot(
        image_path="/tmp/screenshot.png",
        objective="Click the Run button",
    )
    # → {"description": "...", "ui_elements": [...], "next_action": {...}, "source": "openai"}

References:
    - integrations/gemini_vision.py (sibling — Gemini backend)
    - integrations/resilience.py (HybridVisionRouter consumer)
    - skills/etap-gui-agent.md (CUA Loop spec)
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
    logger.info("httpx not installed — OpenAI vision will use urllib fallback")

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.info("Pillow not installed. Run: pip install pillow")


# ─── Constants ─────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0

# System prompt — same contract as Gemini Vision (structured JSON output)
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


# ─── OpenAI Vision Client ──────────────────────────────────────────────────


class OpenAIVisionClient:
    """OpenAI-compatible Vision API client.

    Works with any provider that implements the OpenAI Chat Completions API:
      - OpenAI (api.openai.com)
      - Azure OpenAI (different URL format)
      - Together AI, Groq, LocalAI, vLLM, Ollama, etc.

    Graceful degradation:
        - No API key → enabled=False, all calls return None
        - httpx missing → falls back to urllib
        - API error → returns error dict, never raises
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.model = os.getenv("OPENAI_VISION_MODEL", DEFAULT_MODEL)
        self.timeout = int(os.getenv("OPENAI_TIMEOUT", str(DEFAULT_TIMEOUT)))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))

        # ─── Check user-supplied key from Settings UI (DB) ─────────────────
        # If the user saved a key via /settings, it overrides env vars.
        # This allows end users to enter their own keys without admin access.
        try:
            from services.api_key_store import api_key_store

            user_config = api_key_store.get_key("openai")
            if user_config and user_config.api_key:
                self.api_key = user_config.api_key
                if user_config.base_url:
                    self.base_url = user_config.base_url.rstrip("/")
                if user_config.model_name:
                    self.model = user_config.model_name
                logger.info("OpenAI Vision: using user-supplied key from Settings UI")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not load user-supplied OpenAI key: %s", exc)

        self.enabled = bool(self.api_key and PIL_AVAILABLE)

        if self.enabled:
            logger.info(
                "✅ OpenAI Vision initialized — model: %s, base_url: %s, timeout: %ds",
                self.model,
                self.base_url,
                self.timeout,
            )
        else:
            missing: List[str] = []
            if not self.api_key:
                missing.append("OPENAI_API_KEY")
            if not PIL_AVAILABLE:
                missing.append("pillow")
            logger.info("OpenAI Vision disabled — missing: %s", ", ".join(missing))

    # ─── Public API ────────────────────────────────────────────────────────

    def analyze_screenshot(
        self,
        image: Any,
        objective: str,
        context: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze a screenshot using OpenAI-compatible Vision API.

        Args:
            image: PIL.Image.Image | path-like | bytes
            objective: what the agent is trying to accomplish
            context: optional prior-step summary

        Returns:
            Dict with keys: description, ui_elements, next_action, objective_complete,
            confidence, source. None if client disabled. Dict with "error" key on failure.
        """
        if not self.enabled:
            return None

        pil_image = self._to_pil_image(image)
        if pil_image is None:
            return {"error": "invalid_image", "message": "Could not convert input to PIL Image"}

        # Encode image as base64 data URL
        image_data_url = self._image_to_data_url(pil_image)
        if not image_data_url:
            return {"error": "image_encoding_failed", "message": "Could not encode image to base64"}

        # Build the chat messages — pass the ACTUAL image data URL (not a placeholder)
        user_content = self._build_user_content(objective, context, pil_image.size, image_data_url)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        # Build request payload — WITHOUT response_format for max compatibility.
        # Some providers (freemodel.dev, etc.) return 400 if response_format is set.
        # The system prompt already asks for strict JSON, which is sufficient.
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        # Build headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # Build URL
        url = f"{self.base_url}/chat/completions"

        # Retry loop — first try WITHOUT response_format, then try WITH it
        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._make_request(url, headers, payload)
                return self._parse_response(response)
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "OpenAI Vision attempt %d/%d failed: %s",
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
    def _image_to_data_url(pil_image) -> Optional[str]:
        """Convert PIL Image to base64 data URL.

        Returns: data:image/png;base64,<base64-encoded-png>
        """
        try:
            buffer = io.BytesIO()
            # Resize if too large (OpenAI has a 20MB limit per image)
            max_dim = 1568  # OpenAI's recommended max dimension
            if pil_image.width > max_dim or pil_image.height > max_dim:
                ratio = max_dim / max(pil_image.width, pil_image.height)
                new_size = (int(pil_image.width * ratio), int(pil_image.height * ratio))
                pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)

            pil_image.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
            return f"data:image/png;base64,{b64}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image encoding failed: %s", exc)
            return None

    @staticmethod
    def _build_user_content(
        objective: str,
        context: Optional[str],
        image_size: tuple[int, int],
        image_data_url: str,
    ) -> List[Dict[str, Any]]:
        """Build the user message content with text + image_url.

        Args:
            objective: what the agent is trying to accomplish
            context: optional prior-step summary
            image_size: (width, height) of the screenshot
            image_data_url: the actual data:image/png;base64,... URL
        """
        width, height = image_size
        parts: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    f"OBJECTIVE: {objective}\n"
                    f"SCREENSHOT_SIZE: {width}x{height} pixels\n"
                    + (f"PRIOR_CONTEXT: {context}\n" if context else "")
                    + "Analyze the screenshot and respond with the JSON object described "
                    "in the system instructions. Remember: coordinates must be integers "
                    "within the screenshot bounds, and you MUST return valid JSON only."
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_data_url,
                    "detail": "high",
                },
            },
        ]
        return parts

    def _make_request(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make the HTTP request to the OpenAI-compatible endpoint.

        Uses httpx if available, otherwise falls back to urllib.
        """
        # Inject the actual image data URL (we used PLACEHOLDER in _build_user_content)
        # This is done here to avoid logging the huge base64 string
        if HTTPX_AVAILABLE:
            return self._make_request_httpx(url, headers, payload)
        return self._make_request_urllib(url, headers, payload)

    def _make_request_httpx(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make request using httpx."""
        # Re-encode image (the PLACEHOLDER needs to be replaced with actual data)
        # We re-build the payload here with the real image
        import httpx

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _make_request_urllib(
        self, url: str, headers: Dict[str, str], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fallback: make request using urllib (no external deps)."""
        import urllib.error
        import urllib.request

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)

    @staticmethod
    def _parse_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Parse the OpenAI chat completion response into our standard format.

        Expected response structure:
        {
            "choices": [
                {
                    "message": {
                        "content": "{\"description\": ..., \"next_action\": ...}"
                    }
                }
            ]
        }
        """
        try:
            choices = response.get("choices", [])
            if not choices:
                return {
                    "error": "no_choices",
                    "message": "API returned no choices",
                    "raw": str(response)[:500],
                }

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                return {
                    "error": "empty_content",
                    "message": "API returned empty content",
                    "raw": str(response)[:500],
                }

            # The content should be JSON (we requested response_format: json_object)
            # But some providers wrap it in markdown — strip if needed
            content = content.strip()
            if content.startswith("```"):
                # Remove markdown code fences
                lines = content.split("\n")
                content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

            parsed = json.loads(content)
            parsed["source"] = "openai"
            return parsed

        except json.JSONDecodeError as exc:
            return {
                "error": "json_parse_error",
                "message": f"Could not parse content as JSON: {exc}",
                "raw_content": content[:500] if "content" in dir() else "?",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "error": "parse_error",
                "message": f"{type(exc).__name__}: {exc}",
                "raw": str(response)[:500],
            }


# ─── Module-level singleton ────────────────────────────────────────────────

openai_vision = OpenAIVisionClient()


__all__ = ["OpenAIVisionClient", "openai_vision"]
