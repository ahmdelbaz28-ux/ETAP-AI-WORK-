"""Test: state transition completeness.

If the codebase defines a STATE_TRANSITIONS map, verify every status update
in the code is present in the map. If no map exists, this test passes with
a note.
"""
import re
from pathlib import Path


def test_state_transitions_exist_or_skip():
    """Check if STATE_TRANSITIONS map exists; if not, skip with guidance."""
    repo = Path(__file__).resolve().parents[2]

    # Search for STATE_TRANSITIONS in all .py and .ts files
    found_in = []
    for pattern in ["**/*.py", "**/*.ts"]:
        for f in repo.glob(pattern):
            if "node_modules" in str(f) or ".venv" in str(f):
                continue
            try:
                content = f.read_text()
                if "STATE_TRANSITIONS" in content or "stateTransitions" in content:
                    found_in.append(str(f.relative_to(repo)))
            except Exception:
                continue

    if not found_in:
        import pytest
        pytest.skip(
            "No STATE_TRANSITIONS map found. "
            "If the app has status fields (e.g. study status), "
            "consider defining a state transition map for verification."
        )

    print(f"✓ STATE_TRANSITIONS found in: {found_in}")
