"""
Gemini Vision Integration for AhmedETAP
Provides visual perception for the ETAP GUI Agent (Computer Use Agent).

Sends screenshots to Google's Gemini Vision API and returns structured
descriptions of UI elements, text, icons, and recommended next actions.

Usage:
    from integrations.gemini_vision import gemini_vision

    # Analyze a screenshot
    analysis = gemini_vision.analyze_screenshot(
        image_path="/tmp/before.png",
        objective="Find the Run button and click it to start Load Flow",
    )
    # → {"description": "...", "ui_elements": [...], "next_action": {"type": "click", "x": 420, "y": 320}, ...}

Environment variables:
    GEMINI_API_KEY       — Google AI Studio API key (required)
    GEMINI_MODEL         — Model name (default: gemini-2.0-flash-exp)
    GEMINI_MAX_RETRIES   — Max retries on transient errors (default: 3)
    GEMINI_TIMEOUT       — Per-request timeout in seconds (default: 30)

References:
    - skills/etap-gui-agent.md (Visual Perception Layer)
    - agents/etap_gui_agent.py (CUA Loop consumer)
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Google GenAI SDK (optional dependency) ─────────────────────────────────
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.info("google-generativeai SDK not installed. Run: pip install google-generativeai")

# ─── PIL is needed to convert images to bytes ──────────────────────────────
try:
    import importlib.util

    PIL_AVAILABLE = importlib.util.find_spec("PIL") is not None
except ImportError:
    PIL_AVAILABLE = False
if not PIL_AVAILABLE:
    logger.info("Pillow not installed. Run: pip install pillow")


# ─── Constants ──────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-2.0-flash-exp"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0  # exponential: 2s, 4s, 8s

# System prompt instructing Gemini to return strict JSON describing the screen
# and the next action to take. This is the heart of the Visual Perception Layer.
SYSTEM_PROMPT = """You are the Visual Perception Layer of the ETAP GUI Agent, a Computer Use Agent
that operates engineering desktop applications (ETAP, Revit, AutoCAD, SCADA, QGIS, ArcGIS).

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


class GeminiVisionClient:
    """Singleton-style client wrapping Google's Gemini Vision API.

    Designed to degrade gracefully:
    - No API key → enabled=False, all calls return None
    - SDK missing → enabled=False
    - API error → returns error dict, never raises
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self.timeout = int(os.getenv("GEMINI_TIMEOUT", str(DEFAULT_TIMEOUT)))
        self.max_retries = int(os.getenv("GEMINI_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))

        # ─── Check user-supplied key from Settings UI (DB) ─────────────────
        try:
            from services.api_key_store import api_key_store

            user_config = api_key_store.get_key("gemini")
            if user_config and user_config.api_key:
                self.api_key = user_config.api_key
                if user_config.model_name:
                    self.model_name = user_config.model_name
                logger.info("Gemini Vision: using user-supplied key from Settings UI")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Could not load user-supplied Gemini key: %s", exc)

        self.enabled = bool(self.api_key and GEMINI_AVAILABLE and PIL_AVAILABLE)

        if self.enabled:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(
                    self.model_name,
                    system_instruction=SYSTEM_PROMPT,
                    generation_config={
                        "temperature": 0.1,  # low temperature for deterministic UI analysis
                        "top_p": 0.4,
                        "max_output_tokens": 2048,
                        "response_mime_type": "application/json",
                    },
                )
                logger.info(
                    "✅ Gemini Vision initialized — model: %s, timeout: %ds",
                    self.model_name,
                    self.timeout,
                )
            except Exception as exc:
                self.enabled = False
                logger.warning("Gemini Vision init failed: %s", exc)
        else:
            missing: list[str] = []
            if not self.api_key:
                missing.append("GEMINI_API_KEY")
            if not GEMINI_AVAILABLE:
                missing.append("google-generativeai")
            if not PIL_AVAILABLE:
                missing.append("pillow")
            logger.info("Gemini Vision disabled — missing: %s", ", ".join(missing))

    # ─── Public API ────────────────────────────────────────────────────────

    def analyze_screenshot(
        self,
        image: Any,
        objective: str,
        context: str | None = None,
    ) -> dict[str, Any] | None:
        """Analyze a screenshot and return structured UI description + next action.

        Args:
            image: PIL.Image.Image | path-like | bytes
            objective: what the agent is trying to accomplish
            context: optional prior-step summary (e.g., "Just clicked Run, waiting for results")

        Returns:
            Dict with keys: description, ui_elements, next_action, objective_complete, confidence.
            None if client disabled. Dict with "error" key if API call failed.
        """
        if not self.enabled:
            return None

        pil_image = self._to_pil_image(image)
        if pil_image is None:
            return {"error": "invalid_image", "message": "Could not convert input to PIL Image"}

        prompt = self._build_prompt(objective, context, pil_image.size)

        last_error: str | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.model.generate_content(
                    [prompt, pil_image],
                    request_options={"timeout": self.timeout},
                )
                return self._parse_response(response)
            except Exception as exc:  # noqa: BLE001 — Gemini raises various exception types
                last_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "Gemini Vision attempt %d/%d failed: %s",
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

    def health_check(self) -> dict[str, Any]:
        """Return client status for /health endpoints."""
        return {
            "enabled": self.enabled,
            "model": self.model_name,
            "api_key_set": bool(self.api_key),
            "sdk_available": GEMINI_AVAILABLE,
            "pil_available": PIL_AVAILABLE,
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
            from PIL import Image

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
    def _build_prompt(objective: str, context: str | None, image_size: tuple[int, int]) -> str:
        width, height = image_size
        parts = [
            f"OBJECTIVE: {objective}",
            f"SCREENSHOT_SIZE: {width}x{height} pixels",
        ]
        if context:
            parts.append(f"PRIOR_CONTEXT: {context}")
        parts.append(
            "Analyze the screenshot and respond with the JSON object described in the system "
            "instructions. Remember: coordinates must be integers within the screenshot bounds, "
            "and you MUST return valid JSON only.",
        )
        return "\n".join(parts)

    @staticmethod
    def _parse_response(response: Any) -> dict[str, Any]:
        """Parse Gemini response into a dict. Tries multiple extraction strategies."""
        # Strategy 1: response.text (most reliable when response_mime_type=json)
        try:
            text = response.text
            if text:
                return json.loads(text)
        except (ValueError, AttributeError):
            pass

        # Strategy 2: response.candidates[0].content.parts[0].text
        try:
            candidates = getattr(response, "candidates", None)
            if candidates:
                parts = candidates[0].content.parts
                if parts:
                    return json.loads(parts[0].text)
        except (IndexError, AttributeError, ValueError):
            pass

        return {
            "error": "parse_error",
            "message": "Could not extract JSON from Gemini response",
            "raw": str(response)[:500],
        }


# ─── Module-level singleton — import once, reuse everywhere ────────────────

gemini_vision = GeminiVisionClient()


def encode_screenshot_base64(image_path: str) -> str:
    """Utility: encode a screenshot file as base64 (for embedding in audit logs)."""
    with open(image_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


__all__ = ["GeminiVisionClient", "gemini_vision", "encode_screenshot_base64"]
