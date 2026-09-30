#!/usr/bin/env python3
"""
scripts/check_ai_fallback_guard.py — M4.3 Denial Guard: no raw-LLM fallback.

Fails closed if the deleted raw direct-AI fallback path (or any of its
signatures) is reintroduced into the serving code under ``src/``:

- ``runDirectAi`` / ``getGroundedSystemPrompt`` / ``ENGINEERING_GROUNDING_DIRECTIVE``
- ``grounded_direct_ai_fallback`` execution-mode marker
- the legacy ungrounded prompt text ("Respond with professional engineering analysis")
- ``generateWithFailover`` usage OUTSIDE its sole definition module
  (``src/core/providers.ts``); the function is kept for capability-preserving
  paths only and must never be wired back into a raw answering route.

An unregistered / unreachable capability must fail with
SPECIALIZED_EXECUTION_UNAVAILABLE — never a raw LLM answer (M4.3).
"""

from __future__ import annotations

import re
from pathlib import Path

FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"\brunDirectAi\b", "raw direct-AI fallback function (deleted in M4.3)"),
    (r"\bgetGroundedSystemPrompt\b", "fallback prompt builder (deleted in M4.3)"),
    (r"ENGINEERING_GROUNDING_DIRECTIVE", "grounding directive constant (deleted in M4.3)"),
    (r"grounded_direct_ai_fallback", "raw fallback execution-mode marker (deleted in M4.3)"),
    (
        r"Respond with professional engineering analysis",
        "legacy ungrounded prompt text (forbidden since P3/M4.3)",
    ),
]

# generateWithFailover: allowed ONLY in its definition module.
_FAILOVER_ALLOWED = {"src/core/providers.ts"}
_FAILOVER_PATTERN = re.compile(r"\bgenerateWithFailover\b")

_SKIP_DIRS = {"node_modules", "dist", ".git", "__pycache__"}


def run_ai_fallback_guard(repo_root: Path) -> list[str]:
    """Return a list of violations (empty list = clean)."""
    violations: list[str] = []
    src_root = repo_root / "src"
    if not src_root.exists():
        return violations

    for ts_file in src_root.rglob("*.ts"):
        if any(part in _SKIP_DIRS for part in ts_file.parts):
            continue
        rel = ts_file.relative_to(repo_root).as_posix()
        try:
            text = ts_file.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:  # pragma: no cover - IO failure should fail closed
            violations.append(f"{rel}: unreadable ({exc})")
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern, description in FORBIDDEN_PATTERNS:
                if re.search(pattern, line):
                    violations.append(f"{rel}:{lineno}: {description} — '{line.strip()[:120]}'")
            if _FAILOVER_PATTERN.search(line) and rel not in _FAILOVER_ALLOWED:
                violations.append(
                    f"{rel}:{lineno}: 'generateWithFailover' used outside its definition "
                    f"module (capability-preserving paths only) — '{line.strip()[:120]}'"
                )
    return violations


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    import sys

    root = Path(__file__).resolve().parent.parent
    found = run_ai_fallback_guard(root)
    if found:
        sys.stderr.write("[M4.3 BLOCKED] Raw-LLM fallback guard violations:\n")
        for violation in found:
            sys.stderr.write(f"  x {violation}\n")
        sys.exit(1)
    sys.stdout.write("[OK] M4.3 raw-LLM fallback guard: CLEAN\n")
    sys.exit(0)
