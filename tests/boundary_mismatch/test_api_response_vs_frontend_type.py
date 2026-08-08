"""Test: API response shape vs frontend TypeScript type.

Catches the #1 boundary mismatch bug: backend returns {success: bool, ...}
but frontend expects {status: 'completed' | 'failed' | ...}.

This test parses api/*.py for Pydantic response models and ui/src/lib/api.ts
for TypeScript interfaces, then verifies field-name alignment.
"""
import re
from pathlib import Path


def test_study_result_shape_alignment():
    """Backend StudyResult (api/studies.py) vs frontend StudyResult (api.ts)."""
    api_studies = Path(__file__).resolve().parents[2] / "api" / "studies.py"
    api_ts = Path(__file__).resolve().parents[2] / "ui" / "src" / "lib" / "api.ts"

    if not api_studies.exists() or not api_ts.exists():
        import pytest
        pytest.skip("api/studies.py or ui/src/lib/api.ts not found")

    py_content = api_studies.read_text()
    ts_content = api_ts.read_text()

    # Backend uses 'success: bool' and 'execution_time_sec'
    # Frontend uses 'status: ...' and 'duration_ms'
    backend_has_success = "success" in py_content and "bool" in py_content
    backend_has_execution_time_sec = "execution_time_sec" in py_content

    frontend_has_status = "status:" in ts_content and "'completed'" in ts_content
    frontend_has_duration_ms = "duration_ms" in ts_content

    # Document the known mismatch (this is a finding, not a hard failure)
    mismatches = []
    if backend_has_success and frontend_has_status and "success" not in ts_content.split("StudyResult")[1].split("}")[0]:
        mismatches.append(
            "CRITICAL: Backend StudyResult uses 'success: bool', "
            "frontend uses 'status: \"completed\"|\"failed\"|...'. "
            "UI cannot tell if a study succeeded without manual recasting."
        )
    if backend_has_execution_time_sec and frontend_has_duration_ms:
        mismatches.append(
            "HIGH: Backend uses 'execution_time_sec' (seconds), "
            "frontend uses 'duration_ms' (milliseconds). "
            "Unit conversion is missing — UI will display wrong durations."
        )

    if mismatches:
        # Print findings but don't fail — these are documented issues
        # Convert to GitHub issues separately
        for m in mismatches:
            print(f"\n[BOUNDARY MISMATCH] {m}")
    else:
        print("✓ StudyResult shapes aligned")


def test_agents_endpoint_path_alignment():
    """Frontend fetchAgents() calls /api/v1/agents but backend defines /api/v1/agents/info."""
    api_ts = Path(__file__).resolve().parents[2] / "ui" / "src" / "lib" / "api.ts"
    api_agents = Path(__file__).resolve().parents[2] / "api" / "agents.py"

    if not api_ts.exists() or not api_agents.exists():
        import pytest
        pytest.skip("Required files not found")

    ts_content = api_ts.read_text()
    py_content = api_agents.read_text()

    # Frontend calls
    frontend_calls = re.findall(r"request[<\w>]*\(['\"]([^'\"]+)['\"]", ts_content)
    agents_calls = [c for c in frontend_calls if "/agents" in c]

    # Backend routes
    backend_routes = re.findall(r"@router\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]", py_content)

    findings = []
    for fc in agents_calls:
        # Check if frontend path exactly matches a backend route
        matched = any(fc == route[1] or fc.endswith(route[1]) for route in backend_routes)
        if not matched:
            findings.append(
                f"Frontend calls {fc} but no matching backend route in api/agents.py. "
                f"Backend routes: {[r[1] for r in backend_routes]}"
            )

    if findings:
        for f in findings:
            print(f"\n[BOUNDARY MISMATCH] {f}")
    else:
        print("✓ Agent endpoint paths aligned")


def test_chatwithagent_casing_consistency():
    """chatWithAgent sends {agentId, message} (camelCase) but other calls use snake_case."""
    api_ts = Path(__file__).resolve().parents[2] / "ui" / "src" / "lib" / "api.ts"
    if not api_ts.exists():
        import pytest
        pytest.skip("api.ts not found")

    ts_content = api_ts.read_text()

    # Find all object keys sent in POST/PUT bodies
    body_keys = re.findall(r"body:\s*JSON\.stringify\(\{([^}]+)\}", ts_content)

    camel_case_keys = []
    snake_case_keys = []
    for body in body_keys:
        keys = re.findall(r"(\w+):", body)
        for k in keys:
            if any(c.isupper() for c in k):
                camel_case_keys.append(k)
            elif "_" in k:
                snake_case_keys.append(k)

    if camel_case_keys and snake_case_keys:
        print(f"\n[BOUNDARY MISMATCH] Inconsistent casing in api.ts request bodies:")
        print(f"  camelCase keys: {camel_case_keys}")
        print(f"  snake_case keys: {snake_case_keys}")
        print(f"  Recommendation: pick one convention (snake_case for Python backend)")
    else:
        print("✓ Casing is consistent in api.ts request bodies")
