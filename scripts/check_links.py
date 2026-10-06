#!/usr/bin/env python3
"""
Check Internal Markdown Link Integrity across AhmedETAP Documentation
Validates that all relative markdown links point to existing files on disk.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Matches standard markdown links: [text](target "optional title")
# Ignores image links ![]()
LINK_PATTERN = re.compile(r'(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')

def find_docs_markdown():
    files = list(REPO_ROOT.glob("*.md"))
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.exists():
        for f in docs_dir.rglob("*.md"):
            if "site" not in f.parts and "node_modules" not in f.parts:
                files.append(f)
    return sorted(files)

def check_links():
    md_files = find_docs_markdown()
    total_links = 0
    external_links = 0
    anchor_only_links = 0
    valid_internal = 0
    broken_links = []

    print(f"🔍 Scanning {len(md_files)} documentation files for link integrity...")

    for md_path in md_files:
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"⚠️ Could not read {md_path}: {e}")
            continue

        # Strip code blocks
        clean_content = CODE_BLOCK_PATTERN.sub('', content)

        for match in LINK_PATTERN.finditer(clean_content):
            text = match.group(1).strip()
            raw_target = match.group(2).strip()
            total_links += 1

            if raw_target.startswith("http://") or raw_target.startswith("https://") or raw_target.startswith("mailto:"):
                external_links += 1
                continue

            if raw_target.startswith("#"):
                anchor_only_links += 1
                continue

            # Strip query params & anchor
            target_path_str = raw_target.split("?")[0].split("#")[0]
            if not target_path_str:
                anchor_only_links += 1
                continue

            # Normalize path
            # Case 1: Relative to current file's parent dir
            target_rel = (md_path.parent / target_path_str).resolve()
            # Case 2: Relative to REPO_ROOT (if absolute leading slash or repo root relative)
            target_root = (REPO_ROOT / target_path_str.lstrip("/\\")).resolve()
            # Case 3: Relative to docs root
            target_docs = (REPO_ROOT / "docs" / target_path_str.lstrip("/\\")).resolve()

            if (target_rel.exists()) or (target_root.exists()) or (target_docs.exists()):
                valid_internal += 1
            else:
                rel_source = md_path.relative_to(REPO_ROOT)
                broken_links.append({
                    "source": str(rel_source),
                    "text": text,
                    "target": raw_target,
                    "attempted": str(target_rel)
                })

    print("\n📊 Link Integrity Summary:")
    print(f"   Total Links Analyzed:  {total_links}")
    print(f"   External (HTTP/Mail):  {external_links}")
    print(f"   Internal Same-Page (#): {anchor_only_links}")
    print(f"   Verified Local Links:  {valid_internal}")
    print(f"   Broken Local Targets:  {len(broken_links)}")

    if broken_links:
        print("\n❌ Broken Links Found:")
        for b in broken_links:
            print(f"   - In [{b['source']}]: [{b['text']}]({b['target']})")
        return 1

    print("\n✅ Zero broken internal documentation links! Link integrity verified.")
    return 0

if __name__ == "__main__":
    sys.exit(check_links())
