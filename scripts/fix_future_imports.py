#!/usr/bin/env python3
"""Fix __future__ import placement.
Scans all .py files under the project root and ensures that any
`from __future__ import ...` statements appear before all other imports.
Preserves shebangs (#!) and encoding comments at the top of the file.
"""
import pathlib
import re

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]

FUTURE_RE = re.compile(r"^from __future__ import .+$")
IMPORT_RE = re.compile(r"^(import|from) ")

def fix_file(path: pathlib.Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines()
    # Identify shebang/encoding lines (keep at top)
    header_idx = 0
    while header_idx < len(lines) and (lines[header_idx].startswith("#!") or lines[header_idx].startswith("# -*-")):
        header_idx += 1
    # Extract future imports and other imports
    future_lines = []
    other_imports = []
    rest = []
    for i, line in enumerate(lines[header_idx:], start=header_idx):
        stripped = line.strip()
        if FUTURE_RE.match(stripped):
            future_lines.append(line)
        elif IMPORT_RE.match(stripped):
            other_imports.append(line)
        else:
            rest = lines[i:]
            break
    if not future_lines:
        return False
    # Build new content preserving header and docstring if present
    new_lines = lines[:header_idx] + future_lines + other_imports + rest
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return True

if __name__ == "__main__":
    changed = 0
    for py_file in PROJECT_ROOT.rglob("*.py"):
        if fix_file(py_file):
            print(f"Fixed {py_file}")
            changed += 1
    print(f"Total files updated: {changed}")
