"""
tests/test_ai_fallback_guard.py — M4.3 Gate: denial guard blocks raw fallback return.

Proves the meta-CI guard works:
1. The live repository is clean (the raw fallback path is gone).
2. A PLANTED violation (reintroducing ``runDirectAi``) is detected → build fails.
3. ``generateWithFailover`` is allowed only in its definition module
   (src/core/providers.ts); wiring it back into a route is flagged.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_ai_fallback_guard import run_ai_fallback_guard  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_live_repository_is_clean():
    """The real repo has no raw-LLM fallback signatures under src/."""
    assert run_ai_fallback_guard(REPO_ROOT) == []


def test_planted_direct_ai_fallback_is_detected(tmp_path):
    """Planting the deleted fallback must fail the guard (build-blocking)."""
    _write(
        tmp_path / "src" / "routes" / "agents.ts",
        "async function runDirectAi(rc: unknown) { return rc; }\n",
    )
    violations = run_ai_fallback_guard(tmp_path)
    assert violations, "guard must fail when runDirectAi is reintroduced"
    assert any("runDirectAi" in v for v in violations)

    # Similarly for the grounding directive + execution-mode marker.
    _write(
        tmp_path / "src" / "routes" / "more.ts",
        "const x = 'grounded_direct_ai_fallback';\n",
    )
    violations2 = run_ai_fallback_guard(tmp_path)
    assert any("grounded_direct_ai_fallback" in v for v in violations2)


def test_generate_with_failover_only_allowed_in_definition_module(tmp_path):
    # Allowed: definition module itself.
    _write(
        tmp_path / "src" / "core" / "providers.ts",
        "export async function generateWithFailover(env: Env) { return env; }\n",
    )
    assert run_ai_fallback_guard(tmp_path) == []

    # Flagged: usage inside a route (raw answering path re-wiring attempt).
    _write(
        tmp_path / "src" / "routes" / "agents.ts",
        "const result = await generateWithFailover(env, system, messages);\n",
    )
    violations = run_ai_fallback_guard(tmp_path)
    assert violations
    assert any("outside its definition module" in v for v in violations)
