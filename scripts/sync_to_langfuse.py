
from __future__ import annotations

#!/usr/bin/env python3
"""
Upload all prompts from the prompts/ directory to Langfuse Cloud.

Langfuse Cloud's free Hobby plan supports an UNLIMITED number of prompts,
unlike LangWatch's free plan which is capped at 3 prompts per project.

Each prompt YAML file is uploaded as a Langfuse "chat" prompt with:
- name = handle (e.g. "anomaly_agent")
- type = "chat"
- prompt = list of {role, content} messages
- config = {model, temperature} from the YAML
- isActive = True (this becomes the production/latest version)

If a prompt with the same name already exists in Langfuse, a new version
is created automatically (Langfuse handles versioning on the server side).

Usage:
    export LANGFUSE_PUBLIC_KEY=pk-lf-...
    export LANGFUSE_SECRET_KEY=sk-lf-...
    export LANGFUSE_BASE_URL=https://cloud.langfuse.com   # optional
    python scripts/sync_to_langfuse.py
"""

import base64
import os
import sys
from pathlib import Path

import httpx
import yaml

# ─── Configuration ────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = ROOT / "prompts"

PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
BASE_URL = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
DEFAULT_MODEL = os.environ.get("LANGFUSE_DEFAULT_MODEL", "gpt-4o")

if not PUBLIC_KEY or not SECRET_KEY:
    print("ERROR: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
    sys.exit(1)

# Langfuse uses HTTP Basic auth with public_key:secret_key
_basic = base64.b64encode(f"{PUBLIC_KEY}:{SECRET_KEY}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_basic}",
    "Content-Type": "application/json",
}

# ─── Collect unique prompt handles ────────────────────────────────────────
# `.prompt.yaml` files take priority over plain `.yaml` files when both
# exist for the same handle.
handles: dict[str, Path] = {}
for yaml_file in sorted(PROMPTS_DIR.glob("*.yaml")) + sorted(PROMPTS_DIR.glob("*.prompt.yaml")):
    handle = yaml_file.stem
    if handle.endswith(".prompt"):
        handle = handle[:-7]
    if handle not in handles or str(yaml_file).endswith(".prompt.yaml"):
        handles[handle] = yaml_file

print(f"Endpoint: {BASE_URL}")
print(f"Found {len(handles)} unique prompts to sync.\n")

# ─── Fetch existing prompts from Langfuse ────────────────────────────────
existing_prompts: set[str] = set()
try:
    r = httpx.get(
        f"{BASE_URL}/api/public/v2/prompts",
        headers=HEADERS,
        params={"page": 1, "limit": 100},
        timeout=20,
    )
    if r.status_code == 200:
        data = r.json()
        for p in data.get("data", []):
            existing_prompts.add(p.get("name"))
        print(f"Existing prompts in Langfuse: {len(existing_prompts)}")
        if existing_prompts:
            print(f"  Names: {sorted(existing_prompts)}")
        print()
except Exception as e:
    print(f"Warning: could not list existing prompts: {e}\n")

# ─── Sync loop ────────────────────────────────────────────────────────────
synced = 0
created = 0
updated = 0
failed = 0
failures: list[tuple[str, str]] = []

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

    # Normalize messages into the Langfuse chat format
    chat_messages = [
        {"role": msg.get("role", "user"), "content": msg.get("content", "")} for msg in messages
    ]

    # Build config from YAML metadata
    config: dict = {}
    if parsed.get("model"):
        config["model"] = parsed["model"]
    else:
        config["model"] = DEFAULT_MODEL
    if parsed.get("temperature") is not None:
        config["temperature"] = float(parsed["temperature"])

    payload = {
        "name": handle,
        "type": "chat",
        "prompt": chat_messages,
        "config": config,
        "isActive": True,  # mark as production/latest version
    }

    try:
        r = httpx.post(
            f"{BASE_URL}/api/public/prompts",
            headers=HEADERS,
            json=payload,
            timeout=20,
        )
        if r.status_code in (200, 201):
            if handle in existing_prompts:
                # Server creates a new version automatically when name exists
                print(f"  UPDATED (new version): {handle}  (model={config['model']})")
                updated += 1
            else:
                print(f"  CREATED: {handle}  (model={config['model']})")
                created += 1
            synced += 1
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
    f"Langfuse sync complete: {synced} synced "
    f"({created} created, {updated} updated), {failed} failed",
)
print(f"Dashboard: {BASE_URL}")

if failures:
    print("\nFailures:")
    for h, m in failures:
        print(f"  - {h}: {m}")

sys.exit(0 if failed == 0 else 1)
