#!/usr/bin/env python3
"""
scripts/deploy_to_hf_space.py — Deploy production build to Hugging Face Spaces.
Executes the exact 25-item staging whitelist defined in .github/workflows/cd.yml.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN", "")
if not HF_TOKEN:
    # Attempt to read from .env if present
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("HF_TOKEN="):
                HF_TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

SPACE_REPO = "ahmdelbaz28/AhmedETAP-Platform"
REMOTE_URL = f"https://ahmdelbaz28:{HF_TOKEN}@huggingface.co/spaces/{SPACE_REPO}"


import stat


def _on_rm_error(func, path, exc_info):
    """Clear read-only attribute and retry removal on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    stage_dir = repo_root / "scratch" / "hf_stage"

    print("=" * 60)
    print(f"Deploying to Hugging Face Space: {SPACE_REPO}")
    print("=" * 60)

    if stage_dir.exists():
        if sys.version_info >= (3, 12):
            shutil.rmtree(stage_dir, onexc=lambda func, path, exc: (os.chmod(path, stat.S_IWRITE), func(path)))
        else:
            shutil.rmtree(stage_dir, onerror=_on_rm_error)
    stage_dir.mkdir(parents=True, exist_ok=True)

    # 1) HF frontmatter README (renamed to README.md on Space)
    readme_hf = repo_root / "README.hf.md"
    dockerfile = repo_root / "Dockerfile"
    app_py = repo_root / "hf-space" / "app.py"
    ui_dist_index = repo_root / "ui" / "dist" / "index.html"

    for req_file, desc in [
        (readme_hf, "README.hf.md"),
        (dockerfile, "Dockerfile"),
        (app_py, "hf-space/app.py"),
        (ui_dist_index, "ui/dist/index.html"),
    ]:
        if not req_file.exists():
            sys.stderr.write(f"::error::Required file missing: {desc} ({req_file})\n")
            return 1

    shutil.copy2(readme_hf, stage_dir / "README.md")

    # 2) Root files
    root_files = [
        "Dockerfile",
        ".dockerignore",
        "VERSION",
        "prompts.json",
        "compat.py",
        "alembic.ini",
    ]
    for rf in root_files:
        p = repo_root / rf
        if p.exists():
            shutil.copy2(p, stage_dir / rf)

    # 3) DEPLOY_SHA
    res = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=True
    )
    commit_sha = res.stdout.strip()
    (stage_dir / "DEPLOY_SHA").write_text(commit_sha + "\n", encoding="utf-8")
    print(f"Staged DEPLOY_SHA: {commit_sha}")

    # 4) Directories to copy
    dirs_to_copy = [
        "hf-space",
        "migrations",
        "agents",
        "prompts",
        "core_model",
        "core",
        "engine",
        "load_flow",
        "fault_analysis",
        "coordination",
        "relays",
        "contingency",
        "motor_starting",
        "network_solver",
        "services",
        "api",
        "utils",
        "ai_context_engine",
        "integrations",
        "ml",
        "curves",
        "visualization",
        "reporting",
        "digital_twin",
        "security",
        "gis_integration",
        "adms_control",
        "data",
    ]

    for d in dirs_to_copy:
        src = repo_root / d
        dst = stage_dir / d
        if src.exists() and src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)

    # Clean runtime DB files from data/
    for db_file in (stage_dir / "data").glob("*.db*"):
        try:
            db_file.unlink()
        except Exception:
            pass

    # Clean all __pycache__ and *.pyc files (Hugging Face rejects binary .pyc files)
    for pyc in stage_dir.rglob("*.py[co]"):
        try:
            pyc.unlink()
        except Exception:
            pass
    for pycache in stage_dir.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)

    # 5) Fresh UI build
    shutil.copytree(repo_root / "ui" / "dist", stage_dir / "ui-dist", dirs_exist_ok=True)
    print("Staged UI build: ui-dist/ successfully copied.")

    # 6) Git commit & push
    print("\nPreparing git push to Hugging Face...")
    subprocess.run(["git", "init"], cwd=stage_dir, check=True)
    subprocess.run(["git", "config", "user.name", "AhmedETAP CD"], cwd=stage_dir, check=True)
    subprocess.run(["git", "config", "user.email", "ahmdelbaz28@gmail.com"], cwd=stage_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=stage_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", f"deploy: release {commit_sha[:9]} from GitHub main"],
        cwd=stage_dir,
        check=True,
    )

    print(f"Pushing to Hugging Face Space ({SPACE_REPO})...")
    push_res = subprocess.run(
        ["git", "push", REMOTE_URL, "HEAD:main", "--force"],
        cwd=stage_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    if push_res.returncode != 0:
        sys.stderr.write(f"::error::Git push to Hugging Face failed: {push_res.stderr}\n")
        return push_res.returncode

    print(push_res.stdout)
    print("[SUCCESS] Successfully pushed fresh release to Hugging Face Space!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
