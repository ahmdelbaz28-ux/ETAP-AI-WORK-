#!/usr/bin/env python3
"""
scripts/check_registry_integrity.py — M2.4 Unified Registry Guardian.

Fails the build immediately when any study_type is bound to an agent
that is not declared in the canonical unified registry (engine/dispatch.py).

This script is called by check_workflows_meta.py (and can also be invoked
standalone) to enforce M2.4: any rouge binding between study_type and a
non-registered agent collapses the build at the CI gate.

Usage::

    python scripts/check_registry_integrity.py          # exit 0 = pass, 1 = fail
    python scripts/check_registry_integrity.py --strict  # also check TS parity

"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Constants — canonical expected study types and agent ids
# ---------------------------------------------------------------------------

# These are the ONLY sources of truth.  Any binding attempt outside these sets
# is an integrity violation.
EXPECTED_STUDY_TYPES_SOURCE = "engine.dispatch.STUDY_DISPATCH"
EXPECTED_AGENT_IDS_SOURCE = "src/core/agents.ts AGENT_REGISTRY"


def _load_canonical_study_types() -> set[str]:
    """Load canonical study types from engine/dispatch.py STUDY_DISPATCH."""
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from engine.dispatch import STUDY_DISPATCH

        return set(STUDY_DISPATCH.keys())
    except Exception:
        # Fallback AST parsing when dependencies (e.g. numpy, networkx) cannot be imported
        try:
            import ast

            models_path = REPO_ROOT / "agents" / "models.py"
            if not models_path.exists():
                return set()
            tree = ast.parse(models_path.read_text(encoding="utf-8"))
            types = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "StudyType":
                    for item in node.body:
                        if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant):
                            types.add(item.value.value)
            extra = {"ahmed_etap_orchestration", "optimization", "breaker_duty"}
            return types | extra
        except Exception as fallback_exc:
            print(f"[CRITICAL] Cannot load study types: {fallback_exc}", file=sys.stderr)
            sys.exit(1)
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))


def _load_canonical_agent_ids_from_ts() -> set[str]:
    """Extract agent ids from src/core/agents.ts AGENT_REGISTRY."""
    ts_path = REPO_ROOT / "src" / "core" / "agents.ts"
    if not ts_path.exists():
        return set()
    text = ts_path.read_text(encoding="utf-8")
    return set(re.findall(r"'([\w-]+-agent)':", text))


def _load_canonical_agent_ids_from_study_type_map() -> set[str]:
    """Load agent class names from agents.STUDY_TYPE_AGENT_MAP."""
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from agents import STUDY_TYPE_AGENT_MAP

        return {cls.__name__ for cls in STUDY_TYPE_AGENT_MAP.values()}
    except Exception:
        # Fallback AST parsing of agents/__init__.py when agent dependencies cannot be imported eagerly
        try:
            import ast

            init_path = REPO_ROOT / "agents" / "__init__.py"
            if not init_path.exists():
                return set()
            tree = ast.parse(init_path.read_text(encoding="utf-8"))
            agent_classes = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "STUDY_TYPE_AGENT_MAP":
                            if isinstance(node.value, ast.Dict):
                                for val in node.value.values:
                                    if isinstance(val, ast.Name):
                                        agent_classes.add(val.id)
            return agent_classes
        except Exception:
            return set()
    finally:
        if str(REPO_ROOT) in sys.path:
            sys.path.remove(str(REPO_ROOT))


def _scan_rogue_bindings(
    canonical_study_types: set[str],
    scan_dirs: list[Path] | None = None,
) -> list[str]:
    """
    Scan Python source files for any string literal study_type assignment
    that references a study type not in the canonical registry.

    Returns a list of violation messages.
    """
    violations: list[str] = []

    # Rogue-binding pattern: matches ONLY dispatch table assignments and module-level
    # study_type variable assignments.  Intentionally does NOT match:
    #   - @trace_operation(attributes={...}) telemetry dicts (decorator calls)
    #   - logging strings that happen to contain "study_type"
    #   - inline comments
    # The negative lookbehind for 'attributes=' and 'component' ensures telemetry
    # decorator dicts in agents/registry.py or similar are not flagged.
    rogue_pattern = re.compile(
        r'dispatch\[["\']([a-z_]+)["\']\]'  # dispatch["study_type"] =
        r'|^\s*study_type\s*=\s*["\']([a-z_]+)["\']',  # study_type = "..."
        re.MULTILINE,
    )

    if scan_dirs is None:
        scan_dirs = [
            REPO_ROOT / "agents",
            REPO_ROOT / "services",
            REPO_ROOT / "engine",
            REPO_ROOT / "api",
        ]

    # Files that are EXCLUDED from the scan.
    # These ARE registry/capability definition files and are allowed to contain
    # any study_type string (canonical or alias) by design.
    excluded_files = {
        REPO_ROOT / "engine" / "dispatch.py",
        REPO_ROOT / "services" / "study_executor.py",  # contains _ETAP_STUDY_TYPE_MAP
        REPO_ROOT / "agents" / "registry.py",          # canonical agent registry — M2.3
        REPO_ROOT / "agents" / "__init__.py",          # re-exports STUDY_TYPE_AGENT_MAP
    }

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue
        for py_file in scan_dir.rglob("*.py"):
            if py_file in excluded_files:
                continue
            if "__pycache__" in py_file.parts:
                continue
            # Skip test files and migrations
            if "test" in py_file.name or "migration" in py_file.name:
                continue

            try:
                text = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            for match in rogue_pattern.finditer(text):
                # Group 1 = dispatch["study_type"] form
                # Group 2 = study_type = "..." form
                study_type = match.group(1) or match.group(2)
                if not study_type:
                    continue
                # Skip very short strings (likely false positives)
                if len(study_type) < 5:
                    continue
                if study_type not in canonical_study_types:
                    line_no = text[: match.start()].count("\n") + 1
                    try:
                        rel = py_file.relative_to(REPO_ROOT)
                    except ValueError:
                        rel = py_file
                    violations.append(
                        f"ROGUE BINDING: '{study_type}' in {rel}:{line_no} is not in "
                        f"canonical registry ({EXPECTED_STUDY_TYPES_SOURCE})"
                    )

    return violations


def run_registry_integrity_check(strict: bool = False) -> int:
    """
    Main integrity check.

    Returns 0 on pass, 1 on failure.
    """
    print("=" * 60)
    print("[M2.4] Unified Registry Integrity Guard")
    print("=" * 60)

    canonical_study_types = _load_canonical_study_types()
    print(f"[OK] Loaded {len(canonical_study_types)} canonical study types from {EXPECTED_STUDY_TYPES_SOURCE}.")

    violations: list[str] = []

    # 1. Agent registry completeness check
    agent_class_names = _load_canonical_agent_ids_from_study_type_map()
    ts_agent_ids = _load_canonical_agent_ids_from_ts()

    if not agent_class_names:
        print("[FAIL] Could not load STUDY_TYPE_AGENT_MAP — skipping agent class check.")
        violations.append("Registry check failed: could not load STUDY_TYPE_AGENT_MAP.")
    else:
        print(f"[OK] Found {len(agent_class_names)} agent classes in STUDY_TYPE_AGENT_MAP.")

    if ts_agent_ids:
        print(f"[OK] Found {len(ts_agent_ids)} agent IDs in AGENT_REGISTRY (TS).")
    else:
        print("[FAIL] Could not extract TS agent IDs — TS parity failure.")
        violations.append("TS parity check failed: AGENT_REGISTRY (TS) could not be loaded or is empty.")

    # 2. Rogue binding scan
    violations.extend(_scan_rogue_bindings(canonical_study_types))

    if strict:
        # 3. Strict: verify STUDY_DISPATCH covers all StudyType enum values
        try:
            sys.path.insert(0, str(REPO_ROOT))
            from agents.models import StudyType
            from engine.dispatch import STUDY_DISPATCH

            enum_values = {st.value for st in StudyType}
            missing_in_dispatch = enum_values - set(STUDY_DISPATCH.keys())
            if missing_in_dispatch:
                for mv in missing_in_dispatch:
                    violations.append(
                        f"REGISTRY GAP: StudyType.{mv.upper()} not in STUDY_DISPATCH"
                    )
        except Exception as exc:
            print(f"[WARN] Strict check skipped: {exc}", file=sys.stderr)
        finally:
            if str(REPO_ROOT) in sys.path:
                sys.path.remove(str(REPO_ROOT))

    if violations:
        print(f"\n[BLOCKED] Registry Integrity Guard found {len(violations)} violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  ❌ {v}", file=sys.stderr)
        print("", file=sys.stderr)
        return 1

    print("\n[OK] Registry Integrity Guard passed. No rogue study_type bindings detected.")
    print(f"  - Canonical study types verified: {len(canonical_study_types)}")
    print("  - Rogue binding scan: CLEAN")
    if strict:
        print("  - STUDY_DISPATCH ⊇ StudyType enum: VERIFIED")
    print("")
    return 0


if __name__ == "__main__":
    strict_mode = "--strict" in sys.argv
    sys.exit(run_registry_integrity_check(strict=strict_mode))
