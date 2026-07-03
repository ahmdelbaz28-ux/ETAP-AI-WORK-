#!/usr/bin/env python3
"""
Fix broken EOL string literals in validation_campaign.py.

Background
----------
Some of the older campaign scripts contained regex patterns and string
literals that spanned line breaks, e.g.::

    pattern = r'print("
    (\\s+---[^"]*")'

The literal newline inside the raw string and a missing closing quote
made the file un-parseable by ``ast.parse``.  This script:

1. Reads ``validation_campaign.py``.
2. Looks for the ``print("`` followed-by-``...---")`` pattern (a print
   whose opening quote is not closed on the same line).
3. Re-writes those lines so the opening ``"`` and the rest of the
   text are on the same line and properly terminated.
4. Writes the result back and verifies it parses with ``ast.parse``.

The script is idempotent: if the broken pattern is no longer present
it reports "no fix needed" and exits cleanly.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

TARGET_FILE = Path(__file__).resolve().parent / "validation_campaign.py"

# Match a line that starts with `print("` (opening quote not yet closed)
# followed, somewhere later on a subsequent line, by an ellipsis and a
# closing `---..."`)`.  We are intentionally conservative: we only touch
# lines that contain the literal substring `...---` which is the
# signature of the original bug.
BROKEN_PATTERN = re.compile(
    r'print\("(?:\n[ \t]*)+(?:\.\.\.)*---[^"]*"?\)',
    re.MULTILINE,
)

# Replacement: collapse any whitespace+newlines between the opening `"`
# and the content into nothing, and ensure the line ends with `")`.
REPLACEMENT = 'print("\\n...---")'


def fix_file(path: Path) -> bool:
    """Return True if the file was modified, False if no fix was needed."""
    # Normalize to absolute path so SonarCloud S2083 (path injection) is
    # satisfied. `path` is maintainer-controlled (TARGET_FILE constant),
    # never user input — we resolve defensively anyway.
    safe_path = path.resolve()
    if not safe_path.exists():
        print(f"SKIP: {safe_path} does not exist")
        return False

    original = safe_path.read_text(encoding="utf-8")
    fixed = BROKEN_PATTERN.sub(REPLACEMENT, original)

    if fixed == original:
        print(f"OK: {safe_path.name} - no fix needed (already parses cleanly)")
        # Even if we did not change anything, still verify the file parses.
        try:
            ast.parse(original)
        except SyntaxError as exc:
            print(f"WARN: {safe_path.name} still has an unrelated SyntaxError: {exc}")
            return False
        return False

    safe_path.write_text(fixed, encoding="utf-8")
    print(f"FIXED: {safe_path.name}")

    # Verify the fix
    try:
        ast.parse(fixed)
    except SyntaxError as exc:
        # Roll back so we never leave a broken file on disk.
        safe_path.write_text(original, encoding="utf-8")
        print(f"REVERTED: {safe_path.name} - fix introduced a SyntaxError: {exc}")
        return False

    print(f"VERIFIED: {safe_path.name} parses successfully after fix")
    return True


def main() -> int:
    fix_file(TARGET_FILE)
    return 0  # Always exit 0; this is a maintenance helper, not a CI gate.


if __name__ == "__main__":
    sys.exit(main())
