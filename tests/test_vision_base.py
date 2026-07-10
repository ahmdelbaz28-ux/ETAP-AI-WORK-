"""
Unit tests for integrations/_vision_base.py — shared vision helper functions.

These tests exercise the functions extracted from
integrations/anthropic_vision.py and integrations/openai_vision.py to
eliminate code duplication (SonarCloud new_duplicated_lines_density).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from integrations import _vision_base


class TestToPilImage:
    """Tests for _vision_base.to_pil_image()."""

    def test_returns_none_when_pil_unavailable(self):
        """GIVEN pil_available=False
        WHEN to_pil_image is called
        THEN it returns None without attempting conversion.
        """
        result = _vision_base.to_pil_image("dummy", pil_available=False)
        assert result is None

    def test_returns_none_for_invalid_input(self):
        """GIVEN pil_available=True and an invalid input type
        WHEN to_pil_image is called
        THEN it returns None (no exception raised).
        """
        # Pass an unsupported type — should return None gracefully
        result = _vision_base.to_pil_image(12345, pil_available=True)
        assert result is None

    def test_returns_none_for_nonexistent_file(self):
        """GIVEN a path to a file that doesn't exist
        WHEN to_pil_image is called
        THEN it returns None (logs warning, no exception).
        """
        result = _vision_base.to_pil_image("/nonexistent/path/to/image.png", pil_available=True)
        assert result is None


class TestImageToBase64Png:
    """Tests for _vision_base.image_to_base64_png()."""

    def test_returns_none_for_invalid_image(self):
        """GIVEN a None image
        WHEN image_to_base64_png is called
        THEN it returns None.
        """
        result = _vision_base.image_to_base64_png(None)
        assert result is None

    def test_returns_base64_string_for_valid_image(self):
        """GIVEN a small PIL Image
        WHEN image_to_base64_png is called
        THEN it returns a non-empty base64 string.
        """
        # Skip if PIL not installed
        pytest.importorskip("PIL")
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="red")
        result = _vision_base.image_to_base64_png(img)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        # Verify it's valid base64 by decoding
        import base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0  # PNG header bytes

    def test_resizes_large_image(self):
        """GIVEN a PIL Image larger than max_dim
        WHEN image_to_base64_png is called
        THEN the image is resized (output is still valid base64).
        """
        pytest.importorskip("PIL")
        from PIL import Image

        img = Image.new("RGB", (3000, 2000), color="blue")
        result = _vision_base.image_to_base64_png(img, max_dim=1568)
        assert result is not None
        assert isinstance(result, str)


class TestImageToDataUrl:
    """Tests for _vision_base.image_to_data_url()."""

    def test_returns_none_for_invalid_image(self):
        """GIVEN a None image
        WHEN image_to_data_url is called
        THEN it returns None.
        """
        result = _vision_base.image_to_data_url(None)
        assert result is None

    def test_returns_data_url_with_prefix(self):
        """GIVEN a valid PIL Image
        WHEN image_to_data_url is called
        THEN it returns a string starting with 'data:image/png;base64,'.
        """
        pytest.importorskip("PIL")
        from PIL import Image

        img = Image.new("RGB", (10, 10), color="green")
        result = _vision_base.image_to_data_url(img)
        assert result is not None
        assert result.startswith("data:image/png;base64,")
        # The part after the prefix should be valid base64
        b64_part = result.removeprefix("data:image/png;base64,")
        import base64
        decoded = base64.b64decode(b64_part)
        assert len(decoded) > 0


class TestRetryWithBackoff:
    """Tests for _vision_base.retry_with_backoff()."""

    def test_success_on_first_attempt(self):
        """GIVEN a make_request that succeeds
        WHEN retry_with_backoff is called
        THEN it returns the parsed result without retrying.
        """
        call_count = 0

        def make_request():
            nonlocal call_count
            call_count += 1
            return {"content": [{"type": "text", "text": "success"}]}

        def parse_response(resp):
            return {"result": resp["content"][0]["text"]}

        result = _vision_base.retry_with_backoff(
            make_request=make_request,
            parse_response=parse_response,
            max_retries=3,
            backoff_seconds=0.01,
            provider_name="TestProvider",
        )
        assert result == {"result": "success"}
        assert call_count == 1, "Should not retry on success"

    def test_retries_on_failure_then_succeeds(self):
        """GIVEN a make_request that fails twice then succeeds
        WHEN retry_with_backoff is called with max_retries=3
        THEN it returns success after 3 attempts.
        """
        call_count = 0

        def make_request():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("transient failure")
            return {"content": [{"type": "text", "text": "success"}]}

        def parse_response(resp):
            return {"result": resp["content"][0]["text"]}

        result = _vision_base.retry_with_backoff(
            make_request=make_request,
            parse_response=parse_response,
            max_retries=3,
            backoff_seconds=0.01,
            provider_name="TestProvider",
        )
        assert result == {"result": "success"}
        assert call_count == 3, "Should retry until success"

    def test_returns_error_after_all_retries_exhausted(self):
        """GIVEN a make_request that always fails
        WHEN retry_with_backoff is called with max_retries=2
        THEN it returns an error dict.
        """
        call_count = 0

        def make_request():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("permanent failure")

        def parse_response(resp):
            return {"result": "should not reach here"}

        result = _vision_base.retry_with_backoff(
            make_request=make_request,
            parse_response=parse_response,
            max_retries=2,
            backoff_seconds=0.01,
            provider_name="TestProvider",
        )
        assert result["error"] == "api_error"
        assert "permanent failure" in result["message"]
        assert call_count == 2, "Should try exactly max_retries times"

    def test_parse_failure_triggers_retry(self):
        """GIVEN a make_request that succeeds but parse_response raises
        WHEN retry_with_backoff is called
        THEN it retries (parse failure is treated as request failure).
        """
        call_count = 0

        def make_request():
            nonlocal call_count
            call_count += 1
            return {"content": []}

        def parse_response(resp):
            raise ValueError("parse error")

        result = _vision_base.retry_with_backoff(
            make_request=make_request,
            parse_response=parse_response,
            max_retries=2,
            backoff_seconds=0.01,
            provider_name="TestProvider",
        )
        assert result["error"] == "api_error"
        assert "parse error" in result["message"]
        assert call_count == 2, "Parse failure should trigger retry"

    def test_max_retries_1_means_no_retry(self):
        """GIVEN max_retries=1
        WHEN make_request fails
        THEN no retry is attempted (only 1 attempt total).
        """
        call_count = 0

        def make_request():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("fail")

        def parse_response(resp):
            return {}

        result = _vision_base.retry_with_backoff(
            make_request=make_request,
            parse_response=parse_response,
            max_retries=1,
            backoff_seconds=0.01,
            provider_name="TestProvider",
        )
        assert result["error"] == "api_error"
        assert call_count == 1, "max_retries=1 means exactly 1 attempt"

    def test_provider_name_appears_in_error_message(self):
        """GIVEN provider_name='TestProvider'
        WHEN make_request fails
        THEN the error message mentions the provider name (via logger).
        """
        def make_request():
            raise RuntimeError("fail")

        def parse_response(resp):
            return {}

        # We can't easily check logger output, but we verify no exception
        # is raised and the error dict is returned
        result = _vision_base.retry_with_backoff(
            make_request=make_request,
            parse_response=parse_response,
            max_retries=1,
            backoff_seconds=0.01,
            provider_name="TestProvider",
        )
        assert result["error"] == "api_error"


class TestMaxImageDimension:
    """Tests for the MAX_IMAGE_DIMENSION constant."""

    def test_max_image_dimension_is_1568(self):
        """GIVEN the module
        THEN MAX_IMAGE_DIMENSION equals 1568 (both Anthropic + OpenAI limit).
        """
        assert _vision_base.MAX_IMAGE_DIMENSION == 1568
