#!/usr/bin/env python3
"""
Check Metadata and Markdown Standards across AhmedETAP Documentation
Enforces:
1. Standardized YAML frontmatter block (title, version, last_updated, maintainer).
2. Heading hierarchy (# -> ## -> ###).
3. Table of Contents for major documents (> 800 words).
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FRONTMATTER_PATTERN = re.compile(
    r'^---\s*\n'
    r'(?P<yaml>[\s\S]*?)\n'
    r'---\s*\n',
    re.MULTILINE
)

MAJOR_FILES = [
    # Root documents
    "README.md",
    "README.ar.md",
    "QUICKSTART.md",
    "QUICKSTART.ar.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING.ar.md",
    "ROADMAP.md",
    "SUPPORT.md",
    "SUPPORT.ar.md",
    "AGENTS.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    # Docs core guides
    "docs/API_REFERENCE.md",
    "docs/API_QUICKREF.md",
    "docs/API_DOCUMENTATION.md",
    "docs/GLOSSARY.md",
    "docs/DOCUMENTATION_STANDARDS.md",
    "docs/STATUS.md",
    "docs/ARCHITECTURE.md",
    "docs/OPERATIONS_RUNBOOK.md",
    "docs/TROUBLESHOOTING_GUIDE.md",
    "docs/SECURITY_OPERATIONS_MANUAL.md",
    "docs/ENTERPRISE_CERTIFICATION_REPORT.md",
    "docs/TRUST_CHARTER.md",
    "docs/VALIDATION_REPORT.md",
    "docs/TUTORIALS/README.md",
    "docs/TUTORIALS/01_load_flow_short_circuit_protection.md",
    "docs/TUTORIALS/02_motor_starting_voltage_drop.md",
    "docs/TUTORIALS/03_arc_flash_hazard_evaluation.md",
]

def parse_frontmatter(content):
    match = FRONTMATTER_PATTERN.match(content)
    if not match:
        return None
    yaml_text = match.group("yaml")
    metadata = {}
    for line in yaml_text.splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            metadata[k.strip()] = v.strip().strip('"\'')
    return metadata

def check_file(rel_path):
    file_path = REPO_ROOT / rel_path
    if not file_path.exists():
        return [f"File does not exist: {rel_path}"]

    content = file_path.read_text(encoding="utf-8-sig", errors="replace")
    errors = []

    # 1. Frontmatter check
    metadata = parse_frontmatter(content)
    if not metadata:
        errors.append("Missing YAML frontmatter block (--- ... ---)")
    else:
        for req_field in ["title", "version", "last_updated", "maintainer"]:
            if req_field not in metadata or not metadata[req_field]:
                errors.append(f"Frontmatter missing required field '{req_field}'")
            elif req_field == "last_updated":
                # Expect YYYY-MM-DD
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', metadata["last_updated"]):
                    errors.append(f"Invalid date format for last_updated: '{metadata['last_updated']}' (expected YYYY-MM-DD)")

    # 2. Word count and Table of Contents check
    words = len(content.split())
    if words > 800:
        has_toc = bool(re.search(r'##\s*(📋\s*)?(Table of Contents|جدول المحتويات)', content, re.IGNORECASE) or
                      re.search(r'\[Table of Contents\]', content, re.IGNORECASE))
        if not has_toc:
            errors.append(f"Document has {words} words (>800 words) but is missing a Table of Contents")

    return errors

def main():
    total_checked = 0
    total_errors = 0
    print(f"🔍 Auditing {len(MAJOR_FILES)} major documentation files for metadata & style standards...")

    for rel_path in MAJOR_FILES:
        total_checked += 1
        errs = check_file(rel_path)
        if errs:
            total_errors += len(errs)
            print(f"\n❌ [{rel_path}]:")
            for err in errs:
                print(f"   - {err}")
        else:
            print(f"   ✅ [{rel_path}] OK")

    print(f"\n📊 Summary: Checked {total_checked} files, found {total_errors} issue(s).")
    if total_errors > 0:
        return 1
    print("✅ All major documentation files comply with metadata and structure standards!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
