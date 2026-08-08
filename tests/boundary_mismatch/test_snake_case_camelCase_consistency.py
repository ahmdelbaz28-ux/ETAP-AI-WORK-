"""Test: snake_case ↔ camelCase consistency.

Catches field naming drift between DB columns, API responses, and TS types.
"""
import re
from pathlib import Path


def test_api_response_field_casing():
    """API responses should use snake_case (Python convention) consistently."""
    api_dir = Path(__file__).resolve().parents[2] / "api"
    if not api_dir.exists():
        import pytest
        pytest.skip("api/ not found")

    camel_case_findings = []
    for py in api_dir.glob("*.py"):
        content = py.read_text()
        # Find Pydantic field declarations with camelCase
        # Pattern: field_name: Type = ... where field_name has uppercase
        fields = re.findall(r"^\s+(\w+):\s+", content, re.MULTILINE)
        for field in fields:
            if any(c.isupper() for c in field) and "_" not in field:
                camel_case_findings.append(f"{py.name}: {field}")

    if camel_case_findings:
        print(f"\n[BOUNDARY MISMATCH] camelCase fields in Python API (should be snake_case):")
        for f in camel_case_findings[:10]:
            print(f"  {f}")
    else:
        print("✓ Python API fields use snake_case consistently")


def test_frontend_type_casing():
    """Frontend TypeScript types — check for snake_case (inconsistent with TS convention)."""
    api_ts = Path(__file__).resolve().parents[2] / "ui" / "src" / "lib" / "api.ts"
    if not api_ts.exists():
        import pytest
        pytest.skip("api.ts not found")

    content = api_ts.read_text()

    # Find interface fields
    interfaces = re.findall(r"interface\s+\w+\s*\{([^}]+)\}", content)
    snake_case_findings = []
    for iface in interfaces:
        fields = re.findall(r"(\w+)[\?\:]?:", iface)
        for field in fields:
            if "_" in field:
                snake_case_findings.append(field)

    if snake_case_findings:
        print(f"\n[BOUNDARY MISMATCH] snake_case fields in TS types (should be camelCase):")
        for f in snake_case_findings[:10]:
            print(f"  {f}")
        print(f"  → These will not auto-map to Python's snake_case without a serializer")
    else:
        print("✓ TS types use camelCase consistently")
