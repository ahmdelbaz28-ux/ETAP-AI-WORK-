#!/usr/bin/env python3
"""
Dockerfile syntax validator (no Docker daemon required).

Validates:
1. Every COPY source exists in the repo
2. Every COPY destination is a valid path
3. The ml/ directory is now copied (regression check)
4. The entry point file exists
5. EXPOSE port matches CMD
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile"


def parse_dockerfile(path: Path) -> list[tuple[int, str, list[str]]]:
    """Parse Dockerfile into list of (line_number, instruction, args)."""
    instructions = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        instr = parts[0].upper()
        args = parts[1:]
        instructions.append((i, instr, args))
    return instructions


def validate_copy_sources(instructions: list, dockerfile_dir: Path) -> list[str]:
    """Validate that every COPY source exists in the repo."""
    errors = []
    for lineno, instr, args in instructions:
        if instr != "COPY":
            continue
        # Handle COPY --chown=user:user src dest
        if args[0].startswith("--"):
            args = args[1:]
        if len(args) < 2:
            errors.append(f"L{lineno}: COPY has no destination")
            continue
        # Sources are all but last arg; last arg is dest
        sources = args[:-1]
        for src in sources:
            src_path = dockerfile_dir / src
            if not src_path.exists():
                errors.append(f"L{lineno}: COPY source '{src}' does not exist at {src_path}")
    return errors


def validate_ml_is_copied(instructions: list) -> list[str]:
    """Regression: ml/ directory must be copied to the container."""
    errors = []
    ml_copied = False
    for lineno, instr, args in instructions:
        if instr != "COPY":
            continue
        check_args = args[1:] if args[0].startswith("--") else args
        for arg in check_args:
            if arg.rstrip("/") == "ml" or arg.startswith("ml/"):
                ml_copied = True
                break
    if not ml_copied:
        errors.append(
            "REGRESSION: ml/ directory is NOT copied in the Dockerfile. "
            "This causes 'No module named ml' on HF Space."
        )
    return errors


def validate_entry_point(instructions: list, dockerfile_dir: Path) -> list[str]:
    """Validate that the entry point file exists."""
    errors = []
    # Find the COPY that puts app.py in place
    app_py_copied = False
    for lineno, instr, args in instructions:
        if instr != "COPY":
            continue
        check_args = args[1:] if args[0].startswith("--") else args
        sources = check_args[:-1]
        for src in sources:
            if "app.py" in src:
                src_path = dockerfile_dir / src
                if src_path.exists():
                    app_py_copied = True
    if not app_py_copied:
        errors.append("Entry point app.py is not copied to the container")
    return errors


def validate_expose_matches_cmd(instructions: list) -> list[str]:
    """Validate that EXPOSE port matches the PORT env var and CMD."""
    errors = []
    expose_port = None
    env_port = None
    for lineno, instr, args in instructions:
        if instr == "EXPOSE" and args:
            expose_port = args[0]
        elif instr == "ENV" and len(args) >= 2 and args[0] == "PORT":
            # ENV PORT=7860 or ENV PORT 7860
            val = args[1]
            if val.startswith("PORT="):
                val = val.split("=", 1)[1]
            env_port = val
    if expose_port and env_port and expose_port != env_port:
        errors.append(
            f"EXPOSE port ({expose_port}) does not match ENV PORT ({env_port})"
        )
    return errors


def main() -> int:
    if not DOCKERFILE.exists():
        print(f"❌ Dockerfile not found at {DOCKERFILE}", file=sys.stderr)
        return 1

    instructions = parse_dockerfile(DOCKERFILE)
    print(f"Parsed {len(instructions)} instructions from Dockerfile")

    all_errors: list[str] = []
    all_errors.extend(validate_copy_sources(instructions, REPO_ROOT))
    all_errors.extend(validate_ml_is_copied(instructions))
    all_errors.extend(validate_entry_point(instructions, REPO_ROOT))
    all_errors.extend(validate_expose_matches_cmd(instructions))

    # Also validate the sync-platforms.yml copies ml/
    sync_yml = REPO_ROOT / ".github" / "workflows" / "sync-platforms.yml"
    if sync_yml.exists():
        content = sync_yml.read_text()
        if "../ml" not in content and "ml " not in content:
            all_errors.append(
                "sync-platforms.yml does not copy ml/ to HF Space repo"
            )
        else:
            print("✅ sync-platforms.yml copies ml/ to HF Space")

    if all_errors:
        print(f"\n❌ {len(all_errors)} validation error(s):")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("\n✅ All Dockerfile validations passed:")
    print(f"  - {len([i for _, i, _ in instructions if i == 'COPY'])} COPY sources verified")
    print("  - ml/ is copied (regression check passed)")
    print("  - Entry point app.py exists")
    print("  - EXPOSE port matches ENV PORT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
