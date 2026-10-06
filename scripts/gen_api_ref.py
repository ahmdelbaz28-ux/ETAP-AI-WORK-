#!/usr/bin/env python3
"""
Generate API Quick Reference Cheat-Sheet (docs/API_QUICKREF.md)
from the canonical API Reference (docs/API_REFERENCE.md).

Single Source of Truth: docs/API_REFERENCE.md
"""

import os
import re
from datetime import datetime

CANONICAL_REF = os.path.join("docs", "API_REFERENCE.md")
QUICKREF_OUT = os.path.join("docs", "API_QUICKREF.md")

def parse_api_reference(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Canonical reference not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_section = "General"
    endpoints = []
    
    # Regex to find endpoint headers: ### METHOD /path (Notes)
    endpoint_pattern = re.compile(r"^###\s+(GET|POST|PUT|DELETE|PATCH|WS)\s+([^\s\n]+)(?:\s*\((.*?)\))?")
    section_pattern = re.compile(r"^##\s+(?!#)(.+)$")

    for i, line in enumerate(lines):
        sec_match = section_pattern.match(line.strip())
        if sec_match:
            sec_title = sec_match.group(1).strip()
            if not sec_title.lower().startswith("overview") and not sec_title.lower().startswith("authentication"):
                current_section = sec_title
            continue

        ep_match = endpoint_pattern.match(line.strip())
        if ep_match:
            method = ep_match.group(1).strip()
            path = ep_match.group(2).strip()
            notes = ep_match.group(3) or ""
            
            # Extract summary from following lines
            summary = ""
            for j in range(i + 1, min(i + 10, len(lines))):
                sub_line = lines[j].strip()
                if sub_line.startswith("#") or sub_line.startswith("```"):
                    break
                if sub_line and not sub_line.startswith("**"):
                    summary = sub_line
                    break

            # Anchor tag generation for markdown link
            anchor = re.sub(r"[^a-zA-Z0-9\-_]", "", (method + " " + path + (" " + notes if notes else "")).lower().replace(" ", "-").replace("/", ""))
            # GitHub markdown heading anchor
            clean_anchor = re.sub(r"[^\w\- ]", "", (method + " " + path + (" " + notes if notes else "")).lower()).replace(" ", "-")

            endpoints.append({
                "section": current_section,
                "method": method,
                "path": path,
                "notes": notes,
                "summary": summary,
                "anchor": clean_anchor
            })

    return endpoints

def generate_quickref_markdown(endpoints):
    today = datetime.now().strftime("%Y-%m-%d")
    
    md = [
        "---",
        'title: "AhmedETAP API Quick Reference Cheat-Sheet"',
        'version: "2.1.0"',
        f'last_updated: "{today}"',
        'maintainer: "Eng. Ahmed Elbaz / Platform Team"',
        "---",
        "",
        "# ⚡ AhmedETAP API Quick Reference (Cheat-Sheet)",
        "",
        "> **Note:** This cheat-sheet is automatically derived from the authoritative [API Reference](API_REFERENCE.md).",
        "> For complete request/response JSON schemas, error codes, and field validations, consult [docs/API_REFERENCE.md](API_REFERENCE.md).",
        "",
        "## Table of Contents",
        "- [Authentication Overview](#authentication-overview)",
        "- [Endpoints Quick Reference](#endpoints-quick-reference)",
        "- [Quick cURL Recipes](#quick-curl-recipes)",
        "- [WebSocket Protocol](#websocket-protocol)",
        "",
        "---",
        "",
        "## Authentication Overview",
        "",
        "| Mechanism | Header Format | Typical Use |",
        "| :--- | :--- | :--- |",
        "| **JWT Bearer** | `Authorization: Bearer <jwt_token>` | UI, Interactive Sessions, RBAC |",
        "| **API Key** | `X-API-Key: <api_key>` | Automated CI/CD, Microservices, COM Scripts |",
        "",
        "Obtain token via `POST /api/auth/login` with username & password.",
        "",
        "---",
        "",
        "## Endpoints Quick Reference",
        "",
        "| Method | Endpoint | Category | Description | Canonical Ref |",
        "| :---: | :--- | :--- | :--- | :---: |"
    ]

    for ep in endpoints:
        method_badge = f"`{ep['method']}`"
        notes_str = f" *({ep['notes']})*" if ep['notes'] else ""
        full_endpoint = f"`{ep['path']}`{notes_str}"
        summary = ep['summary'] or "Engineering platform endpoint"
        link = f"[Docs](API_REFERENCE.md#{ep['anchor']})"
        md.append(f"| {method_badge} | {full_endpoint} | {ep['section']} | {summary} | {link} |")

    md.extend([
        "",
        "---",
        "",
        "## Quick cURL Recipes",
        "",
        "### 1. Health & Readiness Probe",
        "```bash",
        "curl -s http://localhost:8000/healthz",
        "curl -s http://localhost:8000/readyz",
        "```",
        "",
        "### 2. Run Newton-Raphson Load Flow",
        "```bash",
        "curl -X POST http://localhost:8000/api/v1/studies/run \\",
        '  -H "Authorization: Bearer $TOKEN" \\',
        '  -H "Content-Type: application/json" \\',
        '  -d \'{"study_type": "LOAD_FLOW", "project_id": "substation_alpha", "parameters": {"max_iterations": 20, "tolerance": 0.0001}}\'',
        "```",
        "",
        "### 3. Run IEC 60909 Short Circuit",
        "```bash",
        "curl -X POST http://localhost:8000/api/v1/studies/run \\",
        '  -H "Authorization: Bearer $TOKEN" \\',
        '  -H "Content-Type: application/json" \\',
        '  -d \'{"study_type": "SHORT_CIRCUIT", "project_id": "substation_alpha", "parameters": {"standard": "IEC_60909", "fault_type": "3PHASE"}}\'',
        "```",
        "",
        "### 4. Query Active Agents Registry",
        "```bash",
        "curl -s http://localhost:8000/api/v1/agents \\",
        '  -H "Authorization: Bearer $TOKEN"',
        "```",
        "",
        "---",
        "",
        "## WebSocket Protocol",
        "",
        "- **Study Streaming:** `ws://localhost:8000/ws/study/{study_id}`",
        "- Subscribes to real-time iteration logs, convergence metrics, and progress percentages.",
        "- See [WebSocket Protocol in API_REFERENCE.md](API_REFERENCE.md#ws-wsstudystudyid).",
        ""
    ])

    return "\n".join(md)

def main():
    import sys
    check_mode = "--check" in sys.argv

    print(f"Parsing {CANONICAL_REF}...")
    endpoints = parse_api_reference(CANONICAL_REF)
    print(f"Discovered {len(endpoints)} API endpoints.")
    
    generated_content = generate_quickref_markdown(endpoints)

    if check_mode:
        if not os.path.exists(QUICKREF_OUT):
            print(f"❌ Check failed: {QUICKREF_OUT} does not exist!")
            sys.exit(1)
        with open(QUICKREF_OUT, "r", encoding="utf-8") as f:
            existing_content = f.read()
        
        # Compare ignoring last_updated line if needed
        gen_lines = [l for l in generated_content.splitlines() if not l.startswith("last_updated:")]
        ex_lines = [l for l in existing_content.splitlines() if not l.startswith("last_updated:")]

        if gen_lines != ex_lines:
            print(f"❌ Check failed: {QUICKREF_OUT} is out of sync with {CANONICAL_REF}!")
            print("Run `python scripts/gen_api_ref.py` to regenerate the cheat-sheet.")
            sys.exit(1)
        print(f"✅ {QUICKREF_OUT} is in sync with canonical {CANONICAL_REF}.")
        sys.exit(0)

    with open(QUICKREF_OUT, "w", encoding="utf-8") as f:
        f.write(generated_content)
    print(f"Generated {QUICKREF_OUT} successfully ({len(generated_content.splitlines())} lines).")

if __name__ == "__main__":
    main()
