"""
Integration tests for ``tests/factories/`` — factory_boy fixture factories.

Verifies:
- Factories produce valid data structures
- Class methods produce correctly shaped outputs
- Sequences, Faker integration, and lazy attributes work
"""

from __future__ import annotations

from typing import Any

import pytest

# factory-boy is in requirements-dev.txt but CI's python-tests job only
# installs requirements.txt + pytest plugins. Skip the entire module if
# factory-boy is not installed (it's a dev-only test).
pytest.importorskip("factory")

from tests.factories.skill_factories import (  # noqa: E402 — after importorskip
    ErrorResponseFactory,
    ExecutionResultFactory,
    SkillDescriptionFactory,
    SkillMetadataFactory,
)


class TestSkillMetadataFactory:
    """factory for SkillMetadata."""

    def test_build_default(self) -> None:
        """Default factory produces a dict with required keys."""
        meta: dict[str, Any] = SkillMetadataFactory.build()
        assert "name" in meta
        assert "version" in meta
        assert "author" in meta
        assert "created_at" in meta

    def test_version_is_semver(self) -> None:
        """Default version is 1.0.0."""
        meta = SkillMetadataFactory.build()
        assert meta["version"] == "1.0.0"

    def test_with_version(self) -> None:
        """with_version class method overrides version."""
        meta = SkillMetadataFactory.with_version(major=2, minor=1, patch=3)
        assert meta["version"] == "2.1.3"

    def test_author_from_faker(self) -> None:
        """Author is a realistic name string."""
        meta = SkillMetadataFactory.build()
        assert isinstance(meta["author"], str)
        assert len(meta["author"]) > 0

    def test_unique_names(self) -> None:
        """Sequence produces unique names."""
        meta1 = SkillMetadataFactory.build()
        meta2 = SkillMetadataFactory.build()
        assert meta1["name"] != meta2["name"]


class TestExecutionResultFactory:
    """factory for ExecutionResult."""

    def test_default_success(self) -> None:
        """Default is a successful result."""
        result = ExecutionResultFactory.build()
        assert result["success"] is True
        assert result["data"] is None

    def test_failed(self) -> None:
        """failed class method produces an error result."""
        result = ExecutionResultFactory.failed(error_type="TimeoutError")
        assert result["success"] is False
        assert result["error"]["type"] == "TimeoutError"

    def test_with_data(self) -> None:
        """with_data class method embeds kwargs as data."""
        result = ExecutionResultFactory.with_data(answer=42, name="test")
        assert result["success"] is True
        assert result["data"]["answer"] == 42
        assert result["data"]["name"] == "test"


class TestErrorResponseFactory:
    """factory for ErrorResponse."""

    def test_defaults(self) -> None:
        """Default is an error response with sensible values."""
        resp = ErrorResponseFactory.build()
        assert resp["error"] is True
        assert resp["type"] == "TestError"
        assert isinstance(resp["message"], str)
        assert len(resp["message"]) > 0


class TestSkillDescriptionFactory:
    """factory for SkillDescription."""

    def test_defaults(self) -> None:
        """Default produces a valid skill description."""
        desc = SkillDescriptionFactory.build()
        assert "name" in desc
        assert "description" in desc
        assert "trigger_words" in desc
        assert isinstance(desc["trigger_words"], list)
        assert len(desc["trigger_words"]) == 3
