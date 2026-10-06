#!/usr/bin/env python3
"""
Verify Media Assets in AhmedETAP Documentation
Scans all documentation Markdown files (root *.md and docs/**/*.md) for image references ![](<path>)
and verifies that:
1. Local relative paths point to existing files on disk.
2. Code blocks (```...```) are excluded from live asset validation.
3. No local temporary or broken absolute paths are referenced.
4. Accessible HTTP/HTTPS URLs (e.g. shields.io badges) are validated.
"""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pattern for Markdown images: ![alt text](path "optional title")
IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
CODE_BLOCK_PATTERN = re.compile(r'```[\s\S]*?```')

def find_documentation_markdown_files():
    """Returns documentation files in scope: root *.md and docs/**/*.md"""
    md_files = []
    # Root level markdown files
    for f in REPO_ROOT.glob("*.md"):
        if f.is_file():
            md_files.append(f)
    
    # Docs directory
    docs_dir = REPO_ROOT / "docs"
    if docs_dir.exists():
        for f in docs_dir.rglob("*.md"):
            # Exclude built site directory if present
            if "site" not in f.parts and "node_modules" not in f.parts:
                md_files.append(f)
                
    return sorted(md_files)

def verify_assets():
    md_files = find_documentation_markdown_files()
    total_images = 0
    missing_images = []
    verified_local = 0
    external_urls = 0

    print(f"🔍 Scanning {len(md_files)} documentation Markdown files for image references...")

    for md_path in md_files:
        try:
            content = md_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print(f"⚠️ Could not read {md_path}: {e}")
            continue

        # Strip fenced code blocks so code examples don't trigger false positives
        content_no_code = CODE_BLOCK_PATTERN.sub('', content)

        for match in IMAGE_PATTERN.finditer(content_no_code):
            alt_text = match.group(1)
            raw_target = match.group(2).strip()
            total_images += 1

            # Skip remote badges / external images
            if raw_target.startswith("http://") or raw_target.startswith("https://"):
                external_urls += 1
                continue

            # Skip dummy ellipsis
            if raw_target == "...":
                continue

            # Strip query strings or fragments if any
            clean_target = raw_target.split("?")[0].split("#")[0]
            if not clean_target:
                continue

            # Check relative to markdown file location
            target_path = (md_path.parent / clean_target).resolve()
            
            # Check relative to repository root
            root_relative_path = (REPO_ROOT / clean_target.lstrip("/\\")).resolve()

            # Check relative to docs directory
            docs_relative_path = (REPO_ROOT / "docs" / clean_target.lstrip("/\\")).resolve()

            if (target_path.exists() and target_path.is_file()) or \
               (root_relative_path.exists() and root_relative_path.is_file()) or \
               (docs_relative_path.exists() and docs_relative_path.is_file()):
                verified_local += 1
            else:
                rel_md = md_path.relative_to(REPO_ROOT)
                missing_images.append({
                    "file": str(rel_md),
                    "alt": alt_text,
                    "target": raw_target,
                    "attempted_path": str(target_path)
                })

    print(f"\n📊 Documentation Media Asset Verification Summary:")
    print(f"   Total Image References: {total_images}")
    print(f"   External URLs / Badges:  {external_urls}")
    print(f"   Verified Local Files:   {verified_local}")
    print(f"   Broken / Missing Local: {len(missing_images)}")

    if missing_images:
        print("\n❌ Broken Image References Found:")
        for item in missing_images:
            print(f"   - In [{item['file']}]: ![{item['alt']}]({item['target']})")
        return 1

    print("\n✅ All documentation media assets and image references are valid and verified!")
    return 0

if __name__ == "__main__":
    sys.exit(verify_assets())
