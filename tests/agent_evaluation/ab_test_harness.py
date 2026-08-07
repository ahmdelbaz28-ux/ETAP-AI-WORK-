"""A/B test harness for agent prompt evaluation.

Runs the same task twice:
- With-prompt: agent loads its prompts/*.yaml system prompt
- Without-prompt (baseline): agent runs with hardcoded default only

Compares outputs against quantitative assertions.
"""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class ABTestResult:
    """Result of a single A/B test run."""
    agent_name: str
    test_case: str
    with_prompt_output: Optional[Dict[str, Any]] = None
    without_prompt_output: Optional[Dict[str, Any]] = None
    with_prompt_score: float = 0.0
    without_prompt_score: float = 0.0
    assertions_passed_with: int = 0
    assertions_passed_without: int = 0
    total_assertions: int = 0
    notes: List[str] = field(default_factory=list)

    @property
    def improvement(self) -> float:
        """Score improvement from prompt (negative = prompt hurt)."""
        return self.with_prompt_score - self.without_prompt_score

    @property
    def improvement_pct(self) -> float:
        """Percentage improvement."""
        if self.without_prompt_score == 0:
            return 0.0
        return (self.improvement / self.without_prompt_score) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "test_case": self.test_case,
            "with_prompt_score": self.with_prompt_score,
            "without_prompt_score": self.without_prompt_score,
            "improvement": self.improvement,
            "improvement_pct": round(self.improvement_pct, 2),
            "assertions_passed_with": self.assertions_passed_with,
            "assertions_passed_without": self.assertions_passed_without,
            "total_assertions": self.total_assertions,
            "notes": self.notes,
        }


def evaluate_assertions(output: Optional[Dict[str, Any]], assertions: List[Dict]) -> tuple:
    """Evaluate output against a list of assertion dicts.

    Each assertion: {"field": "data.bus_voltages", "op": "exists"|"nonempty"|"gt", "value": N}
    Returns (score 0-1, passed_count).
    """
    if not output:
        return 0.0, 0

    passed = 0
    for assertion in assertions:
        field_path = assertion.get("field", "")
        op = assertion.get("op", "exists")
        expected = assertion.get("value")

        # Navigate dotted path
        value = output
        for part in field_path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

        if op == "exists" and value is not None:
            passed += 1
        elif op == "nonempty" and value:
            passed += 1
        elif op == "gt" and value is not None and expected is not None:
            try:
                if float(value) > float(expected):
                    passed += 1
            except (TypeError, ValueError):
                pass
        elif op == "eq" and value == expected:
            passed += 1

    score = passed / len(assertions) if assertions else 0.0
    return score, passed


def run_ab_test(
    agent_name: str,
    test_case: str,
    task_input: Dict[str, Any],
    assertions: List[Dict],
    with_prompt: bool = True,
    without_prompt: bool = True,
) -> ABTestResult:
    """Run an A/B test for an agent.

    NOTE: This is a framework skeleton. Actual agent execution requires:
    1. A running ETAP service (or mock)
    2. LLM API keys for prompt-driven agents
    3. Engineering data (buses, lines, etc.)

    In CI, this function is skipped — see run_ab_test.py for the CLI runner.
    """
    result = ABTestResult(agent_name=agent_name, test_case=test_case)
    result.total_assertions = len(assertions)

    # Check if we can actually run (need LLM + service)
    llm_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not llm_key:
        result.notes.append("SKIPPED: No LLM API key found (OPENAI_API_KEY or ANTHROPIC_API_KEY)")
        return result

    # In a real run, we would:
    # 1. Import the agent class (e.g., LoadFlowAgent)
    # 2. Call agent.execute(task) with the prompt loaded (with_prompt=True)
    # 3. Call agent.execute(task) with prompt disabled (with_prompt=False)
    # 4. Evaluate both outputs against assertions

    result.notes.append("Framework ready — implement agent execution in run_ab_test.py")
    return result


def generate_report(results: List[ABTestResult], output_path: Path) -> None:
    """Generate a JSON report from A/B test results."""
    report = {
        "summary": {
            "total_tests": len(results),
            "avg_improvement_pct": sum(r.improvement_pct for r in results) / len(results) if results else 0,
            "tests_with_improvement": sum(1 for r in results if r.improvement > 0),
            "tests_with_regression": sum(1 for r in results if r.improvement < 0),
        },
        "results": [r.to_dict() for r in results],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))
