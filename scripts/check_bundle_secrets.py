"""
scripts/check_bundle_secrets.py — Scan UI bundle for leaked provider keys (FIX-29).

Ensures that built frontend assets in ui/dist do not contain any hardcoded
or leaked provider secrets (OpenAI sk-, HuggingFace hf_, Vercel vcp_, Supabase sb_, etc.).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}"),
    re.compile(r"hf_[a-zA-Z0-9]{20,}"),
    re.compile(r"vcp_[a-zA-Z0-9]{20,}"),
    re.compile(r"sb_[a-zA-Z0-9]{20,}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{20,}"),
]

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_DIST = _REPO_ROOT / "ui" / "dist"


def scan_directory(dir_path: Path) -> list[tuple[Path, str]]:
    findings: list[tuple[Path, str]] = []
    if not dir_path.exists():
        print(f"[SKIP] Directory {dir_path} does not exist.")
        return findings

    for file_path in dir_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2", ".ttf"):
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern in _SECRET_PATTERNS:
            match = pattern.search(content)
            if match:
                findings.append((file_path, match.group(0)[:8] + "..."))

    return findings


def main() -> int:
    print(f"Scanning {_UI_DIST} for exposed API keys and secrets...")
    findings = scan_directory(_UI_DIST)
    if findings:
        print("[FAIL] CRITICAL: Found exposed secrets in UI bundle:")
        for path, matched in findings:
            print(f"  - {path}: {matched}")
        return 1

    print("[PASS] Zero exposed provider keys detected in UI bundle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
