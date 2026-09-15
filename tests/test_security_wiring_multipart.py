"""Unit tests for RASPMiddleware multipart form field parsing and inspection."""

import inspect

import pytest

from security.wiring import _HAS_STARLETTE, RASPMiddleware


@pytest.mark.skipif(not _HAS_STARLETTE, reason="Starlette required for RASPMiddleware tests")
class TestRASPMultipartParsing:
    """Verify multipart parsing in RASPMiddleware is synchronous and correctly extracts text fields."""

    def test_parse_multipart_is_not_coroutine(self):
        """CRITICAL: _parse_multipart_form_fields must be synchronous, not a coroutine."""
        assert not inspect.iscoroutinefunction(RASPMiddleware._parse_multipart_form_fields)

    def test_extract_multipart_boundary(self):
        """Boundary extraction handles quotes, semicolons, and whitespace."""
        middleware = RASPMiddleware(app=None)
        content_type = 'multipart/form-data; boundary="----WebKitFormBoundary12345"'
        boundary = middleware._extract_multipart_boundary(content_type)
        assert boundary == b"----WebKitFormBoundary12345"

        content_type_no_quotes = "multipart/form-data; boundary=my_custom_boundary; charset=utf-8"
        boundary2 = middleware._extract_multipart_boundary(content_type_no_quotes)
        assert boundary2 == b"my_custom_boundary"

        assert middleware._extract_multipart_boundary("application/json") is None

    def test_parse_multipart_form_fields_extracts_text_fields(self):
        """Text form fields are extracted, binary/file upload sections with filename are skipped."""
        middleware = RASPMiddleware(app=None)
        boundary = "---------------------------974767299852498929531610575"
        content_type = f"multipart/form-data; boundary={boundary}"

        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="username"\r\n\r\n'
            "admin_user\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="comment"\r\n\r\n'
            "Safe test comment\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="test.xml"\r\n'
            "Content-Type: text/xml\r\n\r\n"
            "<data>secret</data>\r\n"
            f"--{boundary}--\r\n"
        ).encode()

        result = middleware._parse_multipart_form_fields(body, content_type)
        assert isinstance(result, dict)
        assert result.get("username") == "admin_user"
        assert result.get("comment") == "Safe test comment"
        assert "file" not in result  # Files should be skipped from form_fields inspection

    @pytest.mark.asyncio
    async def test_middleware_inspects_multipart_body_as_dict_not_coroutine(self):
        """Verify RASPMiddleware passes real dict to engine.inspect, not a coroutine."""
        inspected_payloads = []

        class MockEngine:
            enabled = True

            def inspect(self, data):
                inspected_payloads.append(data)
                return []

        async def dummy_app(scope, receive, send):
            pass

        middleware = RASPMiddleware(app=dummy_app, engine=MockEngine(), public_paths=[])
        boundary = "my_test_boundary_999"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="component_id"\r\n\r\n'
            "transformer_1\r\n"
            f"--{boundary}--\r\n"
        ).encode()

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/components",
            "headers": [
                (b"content-type", f"multipart/form-data; boundary={boundary}".encode()),
                (b"host", b"testserver"),
            ],
            "query_string": b"",
        }

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(msg):
            pass

        await middleware(scope, receive, send)

        assert len(inspected_payloads) == 1
        inspect_data = inspected_payloads[0]
        assert "body" in inspect_data
        assert not inspect.iscoroutine(inspect_data["body"])
        assert isinstance(inspect_data["body"], dict)
        assert inspect_data["body"].get("component_id") == "transformer_1"
