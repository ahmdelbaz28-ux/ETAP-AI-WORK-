#!/usr/bin/env python3
"""
Upload all 31 prompts from the prompts/ directory to LangWatch.

Improvements over the original script:
- Uses X-Auth-Token + X-Project-Id headers (the headers the official
  @langwatch/mcp-server uses), in addition to Authorization: Bearer as a
  fallback.
- Includes the `model` field from each prompt YAML in the payload. This
  bypasses the "No model configured for prompt.create_default
  (ModelNotConfiguredError)" error when no Default Model is set on the
  project, so the upload works whether or not a project-level Default
  Model is configured.
- Falls back to PUT (update) when POST returns 409 (conflict — handle
  already exists), and uses the handle directly in the URL path which
  is supported by the LangWatch REST API.
- Robust YAML parsing with explicit error messages.

Usage:
    export LANGWATCH_API_KEY=sk-lw-...
    export LANGWATCH_PROJECT_ID=project_xxx       # optional override
    python scripts/sync_to_langwatch.py
"""

import os
import sys
from pathlib import Path

import httpx
import yaml

# ─── Configuration ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"

API_KEY = os.environ.get("LANGWATCH_API_KEY", "")
PROJECT_ID = os.environ.get(
    "LANGWATCH_PROJECT_ID", "project_uJ1AuCpZ1p9v849vI_-Ec"
)
BASE_URL = os.environ.get("LANGWATCH_ENDPOINT", "https://app.langwatch.ai")
DEFAULT_MODEL = os.environ.get("LANGWATCH_DEFAULT_MODEL", "gpt-4o")

if not API_KEY:
    print("ERROR: LANGWATCH_API_KEY not set")
    sys.exit(1)

# Use BOTH auth header styles for maximum compatibility. The official MCP
# server uses X-Auth-Token + X-Project-Id; the dashboard REST API also
# accepts Authorization: Bearer.
HEADERS = {
    "X-Auth-Token": API_KEY,
    "X-Project-Id": PROJECT_ID,
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# ─── Collect unique prompt handles ────────────────────────────────────────
# `.prompt.yaml` files take priority over plain `.yaml` files when both
# exist for the same handle.
handles: dict[str, Path] = {}
for yaml_file in sorted(PROMPTS_DIR.glob("*.yaml")) + sorted(
    PROMPTS_DIR.glob("*.prompt.yaml")
):
    handle = yaml_file.stem
    if handle.endswith(".prompt"):
        handle = handle[:-7]
    if handle not in handles or str(yaml_file).endswith(".prompt.yaml"):
        handles[handle] = yaml_file

print(f"Project:  {PROJECT_ID}")
print(f"Endpoint: {BASE_URL}")
print(f"Found {len(handles)} unique prompts to sync.\n")

synced = 0
created = 0
updated = 0
failed = 0
failures: list[tuple[str, str]] = []

# ─── Sync loop ────────────────────────────────────────────────────────────
for handle, yaml_file in sorted(handles.items()):
    try:
        content = yaml_file.read_text(encoding="utf-8")
        parsed = yaml.safe_load(content) or {}
    except Exception as e:
        msg = f"parse error: {e}"
        print(f"  FAILED: {handle} - {msg}")
        failed += 1
        failures.append((handle, msg))
        continue

    messages = parsed.get("messages", [])
    if not messages:
        msg = "no messages found in YAML"
        print(f"  FAILED: {handle} - {msg}")
        failed += 1
        failures.append((handle, msg))
        continue

    lw_messages = [
        {"role": msg.get("role", "user"), "content": msg.get("content", "")}
        for msg in messages
    ]

    # Model from YAML, falling back to the default. Including `model` in the
    # payload is what makes the upload succeed without a project-level
    # Default Model configured.
    model = parsed.get("model") or DEFAULT_MODEL

    payload = {
        "handle": handle,
        "scope": "PROJECT",
        "model": model,
        "messages": lw_messages,
    }

    try:
        # Try POST to create
        r = httpx.post(
            f"{BASE_URL}/api/prompts", headers=HEADERS, json=payload, timeout=20
        )
        if r.status_code in (200, 201):
            print(f"  CREATED: {handle}  (model={model})")
            created += 1
            synced += 1
            continue

        if r.status_code == 409:
            # Already exists — PUT to update (create new version)
            r_put = httpx.put(
                f"{BASE_URL}/api/prompts/{handle}",
                headers=HEADERS,
                json=payload,
                timeout=20,
            )
            if r_put.status_code in (200, 201):
                print(f"  UPDATED: {handle}  (model={model})")
                updated += 1
                synced += 1
                continue
            msg = f"PUT {r_put.status_code}: {r_put.text[:200]}"
            print(f"  FAILED: {handle} - {msg}")
            failed += 1
            failures.append((handle, msg))
            continue

        msg = f"POST {r.status_code}: {r.text[:300]}"
        print(f"  FAILED: {handle} - {msg}")
        failed += 1
        failures.append((handle, msg))

    except Exception as e:
        msg = f"exception: {e}"
        print(f"  FAILED: {handle} - {msg}")
        failed += 1
        failures.append((handle, msg))

# ─── Summary ──────────────────────────────────────────────────────────────
print(f"\n{'=' * 70}")
print(
    f"LangWatch sync complete: {synced} synced "
    f"({created} created, {updated} updated), {failed} failed"
)
print(f"Dashboard: {BASE_URL}/projects/{PROJECT_ID}/prompts")

if failures:
    print("\nFailures:")
    for h, m in failures:
        print(f"  - {h}: {m}")

sys.exit(0 if failed == 0 else 1)
