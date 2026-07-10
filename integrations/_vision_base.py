"""
integrations/_vision_base.py — Shared helpers for vision integration modules.

Extracted from integrations/anthropic_vision.py and integrations/openai_vision.py
to eliminate code duplication (SonarCloud new_duplicated_lines_density).

Both modules had identical:
  - _to_pil_image() static method (coerce image input → PIL.Image)
  - _image_to_base64/_image_to_data_url (resize + base64-encode)
  - retry loop in analyze_screenshot()
  - health_check() return shape

This module provides reusable functions + a RetryMixin that both vision
clients can call, keeping their public API identical while removing the
duplicated code.
"""
from __future__ import annotations

import base64
import io
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Maximum image dimension before auto-resize (both Anthropic + OpenAI use 1568px)
MAX_IMAGE_DIMENSION: int = 1568


def to_pil_image(image: Any, pil_available: bool):
    """Coerce various image inputs into a PIL.Image.Image.

    Args:
        image: PIL.Image, bytes, or path (str/Path)
        pil_available: whether PIL/Pillow is installed (caller's module-level flag)

    Returns:
        PIL.Image.Image or None (if conversion failed or PIL not available)
    """
    if not pil_available:
        return None
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError:
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


def image_to_base64_png(pil_image, max_dim: int = MAX_IMAGE_DIMENSION) -> Optional[str]:
    """Convert PIL Image to base64-encoded PNG string (no data URL prefix).

    Resizes the image if either dimension exceeds `max_dim` (default 1568px).
    Used by Anthropic Vision which expects raw base64 in the source field.
    """
    try:
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError:
        return None
    try:
        buffer = io.BytesIO()
        if pil_image.width > max_dim or pil_image.height > max_dim:
            ratio = max_dim / max(pil_image.width, pil_image.height)
            new_size = (int(pil_image.width * ratio), int(pil_image.height * ratio))
            pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
        pil_image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Image encoding failed: %s", exc)
        return None


def image_to_data_url(pil_image, max_dim: int = MAX_IMAGE_DIMENSION) -> Optional[str]:
    """Convert PIL Image to base64 data URL.

    Returns: data:image/png;base64,<base64-encoded-png>
    Used by OpenAI Vision which expects data URLs in the image_url field.
    """
    b64 = image_to_base64_png(pil_image, max_dim)
    if b64 is None:
        return None
    return f"data:image/png;base64,{b64}"


def retry_with_backoff(
    make_request: Callable[[], dict[str, Any]],
    parse_response: Callable[[dict[str, Any]], dict[str, Any]],
    max_retries: int,
    backoff_seconds: float,
    provider_name: str,
) -> dict[str, Any]:
    """Execute a vision API request with exponential-backoff retries.

    Args:
        make_request: callable that performs the HTTP POST and returns raw JSON
        parse_response: callable that converts raw JSON → result dict
        max_retries: max number of attempts (1 = no retry)
        backoff_seconds: base backoff (multiplied by 2^(attempt-1))
        provider_name: e.g. "Anthropic Vision" / "OpenAI Vision" (for logs)

    Returns:
        Parsed result dict on success, or {"error": "api_error", ...} on failure.
    """
    last_error: Optional[str] = None
    for attempt in range(1, max_retries + 1):
        try:
            response = make_request()
            return parse_response(response)
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "%s attempt %d/%d failed: %s",
                provider_name,
                attempt,
                max_retries,
                last_error,
            )
            if attempt < max_retries:
                time.sleep(backoff_seconds * (2 ** (attempt - 1)))

    return {
        "error": "api_error",
        "message": f"All {max_retries} attempts failed. Last: {last_error}",
    }
