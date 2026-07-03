#!/usr/bin/env python3
"""
Langfuse prompt versioning management for AhmedETAP.

Manages prompt labels (production / staging / experimental) so we can
safely test new prompt versions before promoting them to production.

Usage:
    python scripts/langfuse_prompt_manager.py list
    python scripts/langfuse_prompt_manager.py promote arcflash_agent staging
    python scripts/langfuse_prompt_manager.py demote arcflash_agent staging
    python scripts/langfuse_prompt_manager.py labels arcflash_agent
    python scripts/langfuse_prompt_manager.py versions arcflash_agent
"""

from __future__ import annotations

import argparse
import base64
import os
import sys
from typing import Any

import httpx

# ─── Config ───────────────────────────────────────────────────────────────

PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
BASE_URL = os.environ.get("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

if not PUBLIC_KEY or not SECRET_KEY:
    print("ERROR: LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set")
    sys.exit(1)

_auth = base64.b64encode(f"{PUBLIC_KEY}:{SECRET_KEY}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {_auth}",
    "Content-Type": "application/json",
}

# ─── API helpers ─────────────────────────────────────────────────────────


def _list_prompts() -> list[dict[str, Any]]:
    """List all prompts (v2 API gives name + labels + versions)."""
    r = httpx.get(
        f"{BASE_URL}/api/public/v2/prompts",
        headers=HEADERS,
        params={"page": 1, "limit": 100},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def _list_prompt_versions(name: str) -> list[dict[str, Any]]:
    """List all versions of a prompt (v1 API per-name)."""
    r = httpx.get(
        f"{BASE_URL}/api/public/prompts",
        headers=HEADERS,
        params={"name": name, "page": 1, "limit": 50},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", [])


def _set_label(name: str, version: int, label: str) -> dict[str, Any]:
    """Attach a label to a specific prompt version."""
    r = httpx.post(
        f"{BASE_URL}/api/public/prompts/{name}/versions/{version}/labels",
        headers=HEADERS,
        json={"label": label},
        timeout=20,
    )
    r.raise_for_status()
    return r.json() if r.text else {}


def _remove_label(name: str, version: int, label: str) -> None:
    """Remove a label from a specific prompt version."""
    r = httpx.delete(
        f"{BASE_URL}/api/public/prompts/{name}/versions/{version}/labels/{label}",
        headers=HEADERS,
        timeout=20,
    )
    # 204 = success, 404 = label not present (idempotent)
    if r.status_code not in (204, 404):
        r.raise_for_status()


# ─── Commands ────────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> None:
    prompts = _list_prompts()
    print(f"Total prompts: {len(prompts)}\n")
    print(f"{'Name':<35} {'Type':<6} {'Versions':<10} {'Labels':<30}")
    print("-" * 85)
    for p in prompts:
        name = p.get("name", "")
        ptype = p.get("type", "")
        versions = ",".join(str(v) for v in p.get("versions", []))
        labels = ",".join(p.get("labels", []))
        print(f"{name:<35} {ptype:<6} {versions:<10} {labels:<30}")


def cmd_versions(args: argparse.Namespace) -> None:
    name = args.name
    versions = _list_prompt_versions(name)
    if not versions:
        print(f"Prompt '{name}' has no versions")
        return
    print(f"Versions for '{name}':\n")
    for v in versions:
        version = v.get("version", "?")
        labels = ",".join(v.get("labels", []))
        created = v.get("createdAt", "")
        config = v.get("config", {}) or {}
        model = config.get("model", "unknown")
        print(f"  v{version}: labels=[{labels}], model={model}, created={created}")


def cmd_labels(args: argparse.Namespace) -> None:
    name = args.name
    versions = _list_prompt_versions(name)
    if not versions:
        print(f"Prompt '{name}' has no versions")
        return
    print(f"Labels for '{name}':\n")
    for v in versions:
        version = v.get("version", "?")
        labels = v.get("labels", [])
        if labels:
            print(f"  v{version}: {', '.join(labels)}")


def cmd_promote(args: argparse.Namespace) -> None:
    """Promote the latest version of a prompt to a label.

    Moves the label from any older version to the latest version.
    """
    name = args.name
    label = args.label  # "production" | "staging" | "experimental"

    versions = _list_prompt_versions(name)
    if not versions:
        print(f"ERROR: Prompt '{name}' has no versions")
        sys.exit(1)

    # Latest version = highest version number
    latest = max(versions, key=lambda v: v.get("version", 0))
    latest_version = latest.get("version")

    # Remove the label from any older version that has it
    for v in versions:
        if v.get("version") == latest_version:
            continue
        if label in v.get("labels", []):
            print(f"Removing '{label}' from v{v.get('version')}...")
            _remove_label(name, v.get("version"), label)

    # Add the label to the latest version
    print(f"Promoting '{name}' v{latest_version} to label '{label}'...")
    _set_label(name, latest_version, label)
    print(f"✅ Done. v{latest_version} now has label '{label}'.")


def cmd_demote(args: argparse.Namespace) -> None:
    """Remove a label from all versions of a prompt."""
    name = args.name
    label = args.label

    versions = _list_prompt_versions(name)
    if not versions:
        print(f"Prompt '{name}' has no versions")
        return

    for v in versions:
        if label in v.get("labels", []):
            print(f"Removing '{label}' from v{v.get('version')}...")
            _remove_label(name, v.get("version"), label)
    print(f"✅ Done. Label '{label}' removed from all versions of '{name}'.")


# ─── CLI ─────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage Langfuse prompt versions and labels for AhmedETAP",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all prompts").set_defaults(func=cmd_list)

    p_versions = sub.add_parser("versions", help="Show all versions of a prompt")
    p_versions.add_argument("name", help="Prompt name")
    p_versions.set_defaults(func=cmd_versions)

    p_labels = sub.add_parser("labels", help="Show labels for a prompt")
    p_labels.add_argument("name", help="Prompt name")
    p_labels.set_defaults(func=cmd_labels)

    p_promote = sub.add_parser("promote", help="Promote latest version to a label")
    p_promote.add_argument("name", help="Prompt name")
    p_promote.add_argument(
        "label", choices=["production", "staging", "experimental"], help="Label to assign",
    )
    p_promote.set_defaults(func=cmd_promote)

    p_demote = sub.add_parser("demote", help="Remove a label from all versions")
    p_demote.add_argument("name", help="Prompt name")
    p_demote.add_argument(
        "label", choices=["production", "staging", "experimental"], help="Label to remove",
    )
    p_demote.set_defaults(func=cmd_demote)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
