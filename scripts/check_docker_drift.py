#!/usr/bin/env python3
"""
check_docker_drift.py — verifies Dockerfile COPY sources match cd.yml staging.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile"
CD_YML = REPO_ROOT / ".github" / "workflows" / "cd.yml"


def get_dockerfile_sources() -> set[str]:
    """استخرج أسماء المصادر من أسطر COPY في Dockerfile."""
    sources = set()
    content = DOCKERFILE.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if not line.upper().startswith("COPY"):
            continue
        # أزل كل --flag
        cleaned = re.sub(r"--\S+", "", line).split()
        # cleaned[0]=COPY، cleaned[1:-1]=sources، cleaned[-1]=dest
        if len(cleaned) >= 3:
            for src in cleaned[1:-1]:
                src = src.rstrip("/")
                if not src.startswith("/"):
                    # أزل أي glob (مثل DEPLOY_SHA*) ليطابق الاسم الحقيقي
                    sources.add(os.path.basename(src).rstrip("*?"))
    return sources


def get_staged_items() -> set[str]:
    """استخرج أسماء العناصر المنسوخة في خطوة staging من cd.yml."""
    staged = set()
    content = CD_YML.read_text(encoding="utf-8")
    # ابحث عن أوامر cp -r في خطوة Stage
    for match in re.finditer(r"cp\s+-r\s+([\w\s/.-]+?)(?:stage/|$)", content):
        for item in match.group(1).split():
            item = item.strip().rstrip("/")
            if item and not item.startswith("-"):
                staged.add(os.path.basename(item))
    # العناصر المولّدة برمجياً داخل stage/ (مثل DEPLOY_SHA عبر echo >)
    for match in re.finditer(r">\s*stage/([\w.*?-]+)", content):
        staged.add(match.group(1).rstrip("*?"))
    return staged


def main() -> int:
    dockerfile_sources = get_dockerfile_sources()
    staged_items = get_staged_items()

    # استثناءات معروفة: تُعالَج بشكل مختلف في الـ pipeline
    exempt = {
        "requirements.hf.txt",  # يُنسخ داخل Docker build مباشرة
        "app.py",               # يأتي عبر hf-space/ directory
        "ui-dist",              # يُبنى مسبقاً ويُنزَّل كـ artifact
    }

    missing = sorted(dockerfile_sources - staged_items - exempt)

    if missing:
        print("[ERROR] Drift detected - Dockerfile COPY sources not staged in cd.yml:")
        for m in missing:
            print(f"   ::error:: '{m}' missing from cd.yml staging step")
        print()
        print("Fix: add these to the 'cp -r ...' lines in cd.yml Stage step.")
        return 1

    print(f"[OK] No drift - {len(dockerfile_sources)} Dockerfile sources all staged correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
