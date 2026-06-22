"""
tests/factories/skill_factories.py — Reusable test-fixture factories.

Patterns drawn from factoryboy/factory_boy:
- Factory class per model
- Faker integration for realistic data
- Sequence generation for unique fields
- Factory methods for common states (failed, with_data)
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone

UTC = UTC
from typing import Any, Optional

import factory
from factory import Faker

# ---------------------------------------------------------------------------
# SkillMetadata factory
# ---------------------------------------------------------------------------


class SkillMetadataFactory(factory.Factory):
    """Build ``SkillMetadata`` instances for tests.

    Usage::

        meta = SkillMetadataFactory.build()
        meta = SkillMetadataFactory(author="Eng. Ahmed")

    .. note::
        Replace ``model = dict`` below with ``model = SkillMetadata`` once
        the import path is established.
    """

    class Meta:
        model = dict

    name = factory.Sequence(lambda n: f"skill-{n:04d}")
    version = "1.0.0"
    author = Faker("name")
    created_at = factory.LazyFunction(lambda: datetime.now(UTC))

    @classmethod
    def with_version(cls, major: int = 1, minor: int = 0, patch: int = 0) -> dict[str, Any]:
        return cls(version=f"{major}.{minor}.{patch}")


# ---------------------------------------------------------------------------
# ExecutionResult factory
# ---------------------------------------------------------------------------


class ExecutionResultFactory(factory.Factory):
    """Build execution-result dicts for pipeline tests."""

    class Meta:
        model = dict

    success = True
    data: dict[str, Any] | None = None
    error: dict[str, str] | None = None
    timestamp = factory.LazyFunction(lambda: datetime.now(UTC))

    @classmethod
    def failed(cls, error_type: str = "GenericError") -> dict[str, Any]:
        return cls(
            success=False,
            error={
                "type": error_type,
                "message": "Test error",
                "can_retry": False,
            },
        )

    @classmethod
    def with_data(cls, **kwargs: Any) -> dict[str, Any]:
        return cls(success=True, data=kwargs)


# ---------------------------------------------------------------------------
# ErrorResponse factory
# ---------------------------------------------------------------------------


class ErrorResponseFactory(factory.Factory):
    """Build error-response dicts for API error tests."""

    class Meta:
        model = dict

    error = True
    type = "TestError"
    message = Faker("sentence")
    action_required: str | None = None
    can_retry = False


# ---------------------------------------------------------------------------
# SkillDescription factory
# ---------------------------------------------------------------------------


class SkillDescriptionFactory(factory.Factory):
    """Build valid skill-description dicts."""

    class Meta:
        model = dict

    name = factory.Sequence(lambda n: f"integration-skill-{n:04d}")
    description = factory.Faker("sentence", nb_words=12)
    trigger_words = factory.List([Faker("word") for _ in range(3)])
