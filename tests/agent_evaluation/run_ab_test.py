#!/usr/bin/env python3
"""Run A/B tests for agent evaluation.

Usage:
    OPENAI_API_KEY=... python tests/agent_evaluation/run_ab_test.py

Output:
    tests/agent_evaluation/report.json
"""
import json
import sys
from pathlib import Path

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from tests.agent_evaluation.ab_test_harness import (  # noqa: E402
    ABTestResult,
    generate_report,
    run_ab_test,
)


def main():
    test_cases_path = REPO_ROOT / "tests" / "agent_evaluation" / "test_cases.yaml"
    output_path = REPO_ROOT / "tests" / "agent_evaluation" / "report.json"

    with open(test_cases_path) as f:
        config = yaml.safe_load(f)

    results = []
    for tc in config.get("test_cases", []):
        print(f"\nRunning A/B test: {tc['agent']} — {tc['description']}")
        result = run_ab_test(
            agent_name=tc["agent"],
            test_case=tc["description"],
            task_input=tc["task_input"],
            assertions=tc["assertions"],
        )
        results.append(result)
        print(f"  Score (with prompt):    {result.with_prompt_score:.2f}")
        print(f"  Score (without prompt): {result.without_prompt_score:.2f}")
        print(f"  Improvement: {result.improvement_pct:+.1f}%")

    generate_report(results, output_path)
    print(f"\n✓ Report written to {output_path}")

    # Print summary
    avg = sum(r.improvement_pct for r in results) / len(results) if results else 0
    print(f"\n=== Summary ===")
    print(f"Tests run: {len(results)}")
    print(f"Average improvement: {avg:+.1f}%")


if __name__ == "__main__":
    main()
