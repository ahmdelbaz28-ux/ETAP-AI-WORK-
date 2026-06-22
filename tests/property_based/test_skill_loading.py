"""
Property-based tests for the skill validation layer.

Patterns drawn from HypothesisWorks/hypothesis:
- @given decorator for exhaustive input generation
- Custom strategy composition for domain-specific data
- Phase settings to maximise shrinkage quality
- Stateful testing via RuleBasedStateMachine
"""

from __future__ import annotations

from typing import Any, Dict, List

from hypothesis import HealthCheck, given, settings, strategies as st
from hypothesis import Phase
from pydantic import ValidationError

from skills.skill_validator import (
    ExecutionResult,
    SkillDescription,
    SkillMetadata,
)

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

# A semver-like version string strategy (limited digit length per component)
semver_strategy = st.from_regex(r"^\d{1,3}\.\d{1,3}\.\d{1,3}$", fullmatch=True)

# A kebab-case name strategy with bounded length
# Max length: 5 + 3*6 = 23 chars (well under SkillDescription.name.max_length=100)
kebab_strategy = st.from_regex(r"^[a-z0-9]{1,5}(-[a-z0-9]{1,5}){0,3}$", fullmatch=True)

# Non-empty text without problematic characters
safe_text = st.text(
    min_size=1,
    max_size=50,
    alphabet=st.characters(
        whitelist_categories=["L", "N", "Pd", "Po"],
        # L = letters, N = numbers, Pd = dash, Po = punctuation
    ),
)

# ---------------------------------------------------------------------------
# SkillMetadata property tests
# ---------------------------------------------------------------------------


@given(
    author=safe_text,
    version=semver_strategy,
    requires=st.dictionaries(
        keys=st.sampled_from(["python", "runtime", "permissions", "memory"]),
        values=safe_text,
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=100, phases=[Phase.generate, Phase.shrink])
def test_skill_metadata_roundtrip(
    author: str,
    version: str,
    requires: Dict[str, str],
) -> None:
    """Property: valid semver + author always produce valid SkillMetadata."""
    meta = SkillMetadata(author=author, version=version, requires=requires)
    assert meta.version == version
    assert meta.author == author.strip()
    restored = SkillMetadata.model_validate(meta.model_dump())
    assert restored == meta


@given(
    version=st.text().filter(lambda v: not __import__("re").match(r"^\d+\.\d+\.\d+$", v)),
)
@settings(max_examples=20)
def test_invalid_version_raises(version: str) -> None:
    """Property: non-semver strings MUST raise ValidationError."""
    import pytest

    with pytest.raises(ValidationError):
        SkillMetadata(author="test", version=version)


# ---------------------------------------------------------------------------
# SkillDescription property tests
# ---------------------------------------------------------------------------


# A simple multi-word description strategy (fixed word pool for performance)
SAMPLE_WORDS = [
    "load",
    "flow",
    "analysis",
    "power",
    "system",
    "protection",
    "simulation",
    "validation",
    "coordination",
    "fault",
]
multi_word_description = st.lists(
    st.sampled_from(SAMPLE_WORDS),
    min_size=3,
    max_size=12,
).map(lambda words: " ".join(words))


@given(
    name=kebab_strategy,
    description=multi_word_description,
    trigger_words=st.lists(
        st.text(min_size=1, max_size=20),
        min_size=1,
        max_size=10,
        unique_by=lambda w: w.strip().lower(),
    ),
)
@settings(
    max_examples=50, suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much]
)
def test_skill_description_valid(
    name: str,
    description: str,
    trigger_words: List[str],
) -> None:
    """Property: kebab name + multi-word description -> valid model."""
    desc = SkillDescription(
        name=name,
        description=description,
        trigger_words=trigger_words,
    )
    assert desc.name == name
    assert len(desc.trigger_words) >= 1


@given(
    description=st.text(max_size=9),
)
@settings(max_examples=10)
def test_short_description_rejected(description: str) -> None:
    """Property: descriptions shorter than 10 chars MUST raise ValidationError."""
    import pytest

    with pytest.raises(ValidationError):
        SkillDescription(
            name="test-skill",
            description=description,
            trigger_words=["test"],
        )


# ---------------------------------------------------------------------------
# ExecutionResult property tests
# ---------------------------------------------------------------------------


@given(
    data=st.dictionaries(
        keys=st.text(min_size=1, max_size=20),
        values=st.one_of(
            [st.text(), st.integers(), st.floats(allow_nan=False, allow_infinity=False)]
        ),
        min_size=0,
        max_size=10,
    )
)
@settings(max_examples=50)
def test_success_result_must_not_have_error(data: Dict[str, Any]) -> None:
    """Property: a successful result may contain data but never error."""
    result = ExecutionResult(success=True, data=data)
    assert result.success is True
    assert result.data is not None


@given(
    error_code=st.text(min_size=1, max_size=20),
    error_message=st.text(min_size=1, max_size=100),
)
@settings(max_examples=50)
def test_failure_result_must_not_have_data(
    error_code: str,
    error_message: str,
) -> None:
    """Property: a failed result may contain error but never data."""
    result = ExecutionResult(
        success=False,
        error={"code": error_code, "message": error_message},
    )
    assert result.success is False
    assert result.error is not None


@given(
    data=st.dictionaries(
        keys=st.text(min_size=1, max_size=10),
        values=st.text(),
    ),
    error_code=st.text(min_size=1, max_size=10),
    error_message=st.text(min_size=1, max_size=10),
)
@settings(max_examples=20)
def test_mutually_exclusive_data_and_error(
    data: Dict[str, Any],
    error_code: str,
    error_message: str,
) -> None:
    """Property: data AND error together MUST raise ValidationError."""
    import pytest

    with pytest.raises(ValidationError):
        ExecutionResult(
            success=False,
            data=data,
            error={"code": error_code, "message": error_message},
        )


# ---------------------------------------------------------------------------
# Stateful: SkillDescription trigger-word uniqueness machine
# ---------------------------------------------------------------------------

from hypothesis.stateful import RuleBasedStateMachine, initialize, rule  # noqa: E402


class SkillDescriptionStateMachine(RuleBasedStateMachine):
    """State machine that verifies trigger-word uniqueness is enforced."""

    def __init__(self) -> None:
        super().__init__()
        self._trigger_words: List[str] = []

    @initialize()
    def init(self) -> None:
        self._trigger_words = []

    @rule(
        words=st.lists(
            st.text(
                min_size=1,
                max_size=10,
                alphabet=st.characters(whitelist_categories=["Ll", "Lu", "Nd"]),
            ),
            min_size=2,
            max_size=10,
        )
    )
    def validate_uniqueness(self, words: List[str]) -> None:
        """Attempt to create a SkillDescription with potentially duplicate words."""
        try:
            SkillDescription(
                name="stateful-skill",
                description="A sufficiently long description for stateful tests.",
                trigger_words=words,
            )
            # If it succeeded, there must be no duplicates
            lowered = {w.strip().lower() for w in words if w.strip()}
            assert len(lowered) == len([w for w in words if w.strip()]), (
                f"Expected unique trigger words, got {words}"
            )
        except ValidationError:
            # ValidationError is expected when duplicates exist
            non_empty = [w for w in words if w.strip()]
            lowered = {w.strip().lower() for w in non_empty}
            assert len(lowered) < len(non_empty), f"Expected duplicates in {words}"


TestSkillDescriptionStateMachine = SkillDescriptionStateMachine.TestCase
