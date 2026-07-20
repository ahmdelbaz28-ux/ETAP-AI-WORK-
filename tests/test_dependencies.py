"""
Unit tests for api/dependencies.py — FastAPI dependency injection helpers.

Tests the pure functions and models (PaginationParams, CurrentUser,
_extract_bearer_token) without needing database or external services.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.dependencies import (
    CurrentUser,
    PaginationParams,
    _extract_bearer_token,
    pagination_params,
)


class TestPaginationParams:
    """Tests for the PaginationParams model."""

    def test_default_values(self):
        """GIVEN no arguments
        WHEN PaginationParams is created
        THEN page=1, page_size=20.
        """
        p = PaginationParams()
        assert p.page == 1
        assert p.page_size == 20

    def test_custom_values(self):
        """GIVEN page=3, page_size=50
        WHEN PaginationParams is created
        THEN the values are stored.
        """
        p = PaginationParams(page=3, page_size=50)
        assert p.page == 3
        assert p.page_size == 50

    def test_offset_first_page(self):
        """GIVEN page=1, page_size=20
        WHEN offset is calculated
        THEN it equals 0.
        """
        p = PaginationParams(page=1, page_size=20)
        assert p.offset == 0

    def test_offset_second_page(self):
        """GIVEN page=2, page_size=20
        WHEN offset is calculated
        THEN it equals 20.
        """
        p = PaginationParams(page=2, page_size=20)
        assert p.offset == 20

    def test_offset_third_page(self):
        """GIVEN page=3, page_size=50
        WHEN offset is calculated
        THEN it equals 100.
        """
        p = PaginationParams(page=3, page_size=50)
        assert p.offset == 100

    def test_page_must_be_positive(self):
        """GIVEN page=0
        WHEN PaginationParams is created
        THEN it raises validation error (page must be >= 1).
        """
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_page_size_cannot_exceed_100(self):
        """GIVEN page_size=101
        WHEN PaginationParams is created
        THEN it raises validation error (page_size must be <= 100).
        """
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginationParams(page_size=101)

    def test_page_size_must_be_positive(self):
        """GIVEN page_size=0
        WHEN PaginationParams is created
        THEN it raises validation error.
        """
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginationParams(page_size=0)

    def test_frozen_model(self):
        """GIVEN a PaginationParams instance
        WHEN an attribute is modified
        THEN it raises ValidationError (frozen=True).
        """
        p = PaginationParams(page=1, page_size=20)
        from pydantic import ValidationError
        with pytest.raises((ValidationError, AttributeError)):
            p.page = 5  # type: ignore[misc]


class TestPaginationParamsFactory:
    """Tests for the pagination_params() FastAPI dependency."""

    def test_returns_pagination_params(self):
        """GIVEN default page and page_size
        WHEN pagination_params is called
        THEN it returns a PaginationParams instance.
        """
        result = pagination_params(page=1, page_size=20)
        assert isinstance(result, PaginationParams)
        assert result.page == 1
        assert result.page_size == 20

    def test_custom_values(self):
        """GIVEN page=5, page_size=10
        WHEN pagination_params is called
        THEN it returns PaginationParams with those values.
        """
        result = pagination_params(page=5, page_size=10)
        assert result.page == 5
        assert result.page_size == 10
        assert result.offset == 40


class TestCurrentUser:
    """Tests for the CurrentUser model."""

    def test_create_user(self):
        """GIVEN user_id, username, email, and role
        WHEN CurrentUser is created
        THEN the values are stored.
        """
        user = CurrentUser(
            user_id="u1",
            username="testuser",
            email="test@example.com",
            role="admin",
        )
        assert user.user_id == "u1"
        assert user.email == "test@example.com"
        assert user.role == "admin"


class TestExtractBearerToken:
    """Tests for _extract_bearer_token()."""

    def test_extracts_valid_token(self):
        """GIVEN 'Bearer abc123'
        WHEN _extract_bearer_token is called
        THEN it returns 'abc123'.
        """
        token = _extract_bearer_token("Bearer abc123")
        assert token == "abc123"

    def test_case_insensitive_bearer_prefix(self):
        """GIVEN 'bearer abc123' (lowercase)
        WHEN _extract_bearer_token is called
        THEN it returns 'abc123'.
        """
        token = _extract_bearer_token("bearer abc123")
        assert token == "abc123"

    def test_case_insensitive_bearer_uppercase(self):
        """GIVEN 'BEARER abc123'
        WHEN _extract_bearer_token is called
        THEN it returns 'abc123'.
        """
        token = _extract_bearer_token("BEARER abc123")
        assert token == "abc123"

    def test_missing_bearer_prefix_raises(self):
        """GIVEN 'abc123' (no Bearer prefix)
        WHEN _extract_bearer_token is called
        THEN it raises HTTPException 401.
        """
        with pytest.raises(HTTPException) as exc_info:
            _extract_bearer_token("abc123")
        assert exc_info.value.status_code == 401

    def test_wrong_scheme_raises(self):
        """GIVEN 'Basic abc123' (wrong scheme)
        WHEN _extract_bearer_token is called
        THEN it raises HTTPException 401.
        """
        with pytest.raises(HTTPException) as exc_info:
            _extract_bearer_token("Basic abc123")
        assert exc_info.value.status_code == 401

    def test_empty_string_raises(self):
        """GIVEN an empty string
        WHEN _extract_bearer_token is called
        THEN it raises HTTPException 401.
        """
        with pytest.raises(HTTPException) as exc_info:
            _extract_bearer_token("")
        assert exc_info.value.status_code == 401

    def test_only_bearer_prefix_returns_empty(self):
        """GIVEN 'Bearer ' (no token after prefix)
        WHEN _extract_bearer_token is called
        THEN it returns an empty string (the split produces ['', '']).
        """
        # "Bearer " splits into ["Bearer", ""] — len=2, returns ""
        token = _extract_bearer_token("Bearer ")
        assert token == ""

    def test_token_with_spaces_raises(self):
        """GIVEN 'Bearer token with spaces'
        WHEN _extract_bearer_token is called
        THEN it raises HTTPException 401 (only 1 space allowed).
        """
        with pytest.raises(HTTPException) as exc_info:
            _extract_bearer_token("Bearer token with spaces")
        assert exc_info.value.status_code == 401

    def test_jwt_token_extraction(self):
        """GIVEN a JWT-like token
        WHEN _extract_bearer_token is called
        THEN it returns the full JWT string.
        """
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123"
        result = _extract_bearer_token(f"Bearer {jwt_token}")
        assert result == jwt_token
