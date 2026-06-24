"""
skills/skill_validator.py — Pydantic-powered skill metadata,
description, and execution-result models.

Patterns drawn from pydantic/pydantic (v2):
- BaseModel for declarative data schemas
- Field validation via @field_validator and Annotated
- Model serialization via model_dump / model_json_schema
- Error handling with ValidationError
- Generic models for reusability
"""

from __future__ import annotations

import re
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Generic wrapper — reusable across all skill-related endpoints
# ---------------------------------------------------------------------------

T = TypeVar("T")


class SkillResponse(BaseModel, Generic[T]):  # noqa: UP046
    """Generic envelope for every skill-related API response.

    Usage::

        resp = SkillResponse[SkillDescription](
            data=SkillDescription(...),
            status="ok",
        )
        schema = SkillResponse[SkillDescription].model_json_schema()
    """

    data: T
    status: str = "ok"
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# SkillMetadata — immutable versioned metadata
# ---------------------------------------------------------------------------

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


class SkillMetadata(BaseModel):
    """Versioned metadata attached to every skill.

    >>> meta = SkillMetadata(
    ...     author="Ahmed Elbaz",
    ...     version="1.0.0",
    ...     requires={"python": ">=3.12", "permissions": "read"},
    ... )
    >>> meta.version
    '1.0.0'
    """

    author: str = Field(min_length=1, max_length=128)
    version: str = Field(
        min_length=5,
        max_length=30,
        description="Semantic version string (MAJOR.MINOR.PATCH)",
    )
    requires: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of dependency names to version specifiers",
    )

    @field_validator("version")
    @classmethod
    def version_must_be_semver(cls, v: str) -> str:
        if not SEMVER_PATTERN.match(v):
            raise ValueError(f"'{v}' is not a valid semver string (expected MAJOR.MINOR.PATCH)")
        return v

    @field_validator("author")
    @classmethod
    def author_must_not_be_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("author must not be blank")
        return stripped


# ---------------------------------------------------------------------------
# SkillDescription — the human-facing definition of a skill
# ---------------------------------------------------------------------------

MIN_DESCRIPTION_LENGTH = 10


class SkillDescription(BaseModel):
    """Descriptive name, purpose, and trigger words for an AI agent skill.

    >>> desc = SkillDescription(
    ...     name="load-flow-analysis",
    ...     description="Performs Newton-Raphson load flow on a given power system.",
    ...     trigger_words=["load flow", "power flow", "voltage profile"],
    ... )
    >>> desc.name
    'load-flow-analysis'
    """

    model_config = {"extra": "forbid"}  # reject unknown fields

    name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$",
        description="Kebab-case skill identifier",
    )
    description: str = Field(
        min_length=MIN_DESCRIPTION_LENGTH,
        max_length=2000,
        description="Long-form explanation of what the skill does",
    )
    trigger_words: List[str] = Field(
        min_length=1,
        max_length=50,
        description="Phrases that cause the agent to activate this skill",
    )

    @field_validator("description")
    @classmethod
    def description_should_be_substantial(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped.split()) < 3:
            raise ValueError("description must contain at least three words to be meaningful")
        return stripped

    @model_validator(mode="after")
    def ensure_trigger_words_are_unique(self) -> SkillDescription:
        seen: set[str] = set()
        duplicates = []
        for w in self.trigger_words:
            lowered = w.strip().lower()
            if lowered in seen:
                duplicates.append(w)
            seen.add(lowered)
        if duplicates:
            raise ValueError(f"Duplicate trigger words are not allowed: {duplicates}")
        return self


# ---------------------------------------------------------------------------
# ExecutionResult — the outcome of running a skill
# ---------------------------------------------------------------------------


class ExecutionResult(BaseModel):
    """Result envelope for a completed skill execution.

    >>> ok = ExecutionResult(success=True, data={"answer": 42})
    >>> ok.success
    True

    >>> err = ExecutionResult(
    ...     success=False,
    ...     error={"code": "TIMEOUT", "message": "Skill took too long"},
    ... )
    >>> err.error["code"]
    'TIMEOUT'
    """

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None

    @model_validator(mode="after")
    def mutually_exclusive_data_and_error(self) -> ExecutionResult:
        """Ensure data and error are never both populated."""
        if self.data is not None and self.error is not None:
            raise ValueError("Cannot have both 'data' and 'error' in a result")
        if not self.success and self.data is not None:
            raise ValueError("A failed result must not carry 'data'")
        return self


# ---------------------------------------------------------------------------
# SkillDefinition — aggregates metadata and description
# ---------------------------------------------------------------------------


class SkillDefinition(BaseModel):
    """Top-level definition that ties metadata to a description.

    This is the primary schema used when registering a new skill.
    """

    metadata: SkillMetadata
    description: SkillDescription

    def summarize(self) -> str:
        return f"Skill '{self.description.name}' v{self.metadata.version} by {self.metadata.author}"
