#!/usr/bin/env python3
"""
Upload all prompts from the prompts/ directory to LangWatch.

Uses LangWatch REST API directly for reliable sync.
"""

import os
import sys
from pathlib import Path
import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"
API_KEY = os.environ.get("LANGWATCH_API_KEY", "")
BASE_URL = "https://app.langwatch.ai"

if not API_KEY:
    print("ERROR: LANGWATCH_API_KEY not set")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

synced = 0
failed = 0
created = 0
updated = 0

# Collect unique handles (handle -> filepath mapping)
handles = {}
for yaml_file in sorted(PROMPTS_DIR.glob("*.yaml")) + sorted(PROMPTS_DIR.glob("*.prompt.yaml")):
    handle = yaml_file.stem
    if handle.endswith(".prompt"):
        handle = handle[:-7]
    # .prompt.yaml files take priority over plain .yaml
    if handle not in handles or str(yaml_file).endswith(".prompt.yaml"):
        handles[handle] = yaml_file

print(f"Syncing {len(handles)} unique prompts to LangWatch...\n")

for handle, yaml_file in sorted(handles.items()):
    try:
        content = yaml_file.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
    except Exception as e:
        print(f"  FAILED: {handle} - parse error: {e}")
        failed += 1
        continue

    messages = parsed.get("messages", [])

    lw_messages = []
    for msg in messages:
        lw_messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
        })

    # Minimal payload: only handle, scope, messages
    payload = {
        "handle": handle,
        "scope": "PROJECT",
        "messages": lw_messages,
    }

    try:
        # Try POST to create
        r = httpx.post(f"{BASE_URL}/api/prompts", headers=HEADERS, json=payload, timeout=15)
        if r.status_code in (200, 201):
            print(f"  CREATED: {handle}")
            created += 1
            synced += 1
        elif r.status_code == 409:
            # Already exists - try GET to find ID, then PUT (update/create new version)
            try:
                r_get = httpx.get(f"{BASE_URL}/api/prompts", headers=HEADERS, timeout=15)
                if r_get.status_code == 200:
                    all_prompts = r_get.json()
                    prompt_id = None
                    for p in all_prompts:
                        if p.get("handle") == handle or p.get("id") == handle:
                            prompt_id = p.get("id") or p.get("handle")
                            break
                    if prompt_id:
                        r_put = httpx.put(
                            f"{BASE_URL}/api/prompts/{prompt_id}",
                            headers=HEADERS,
                            json=payload,
                            timeout=15
                        )
                        if r_put.status_code in (200, 201):
                            print(f"  UPDATED: {handle}")
                            updated += 1
                            synced += 1
                        else:
                            print(f"  FAILED: {handle} - PUT {r_put.status_code}: {r_put.text[:200]}")
                            failed += 1
                    else:
                        print(f"  FAILED: {handle} - not found in existing prompts list")
                        failed += 1
                else:
                    print(f"  FAILED: {handle} - list failed: {r_get.status_code}")
                    failed += 1
            except Exception as e:
                print(f"  FAILED: {handle} - update: {e}")
                failed += 1
        else:
            print(f"  FAILED: {handle} - POST {r.status_code}: {r.text[:300]}")
            failed += 1
    except Exception as e:
        print(f"  FAILED: {handle} - {e}")
        failed += 1

print(f"\n{'='*60}")
print(f"LangWatch sync complete: {synced} synced ({created} created, {updated} updated), {failed} failed")
print(f"Dashboard: {BASE_URL}")
sys.exit(0 if failed == 0 else 1)