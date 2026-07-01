#!/usr/bin/env python3
"""Verify all external service connections."""

import os

import httpx

print("=" * 60)
print("SERVICE VERIFICATION REPORT")
print("=" * 60)

# 1. Smithery
print("\n--- Smithery ---")
s_api_key = os.environ.get("SMITHERY_API_KEY", "")
s_headers = {"Authorization": f"Bearer {s_api_key}", "User-Agent": "AhmedETAP/1.0.0"}

try:
    r = httpx.get("https://api.smithery.ai/servers", headers=s_headers, timeout=10)
    print(f"  Status: {r.status_code}")
    if r.status_code == 200:
        servers = r.json().get("servers", [])
        print(f"  Available servers: {len(servers)}")
        for s in servers[:5]:
            print(f"    - {s.get('displayName', '?')} ({s.get('qualifiedName', '?')})")
        print(f"    ... and {len(servers) - 5} more" if len(servers) > 5 else "")
    else:
        print(f"  Error: {r.text[:200]}")
except Exception as e:
    print(f"  Connection failed: {e}")

# 2. LangWatch
print("\n--- LangWatch ---")
l_api_key = os.environ.get("LANGWATCH_API_KEY", "")
l_headers = {"Authorization": f"Bearer {l_api_key}", "Content-Type": "application/json"}

try:
    r = httpx.get("https://app.langwatch.ai/api/prompts", headers=l_headers, timeout=10)
    print(f"  Prompts API: {r.status_code}")
    if r.status_code == 200:
        prompts = r.json()
        print(f"  Registered prompts: {len(prompts)}")
        for p in prompts:
            print(f"    - {p.get('handle', '?')} (id: {p.get('id', '?')[:20]}...)")
    else:
        print(f"  Error: {r.text[:200]}")
except Exception as e:
    print(f"  Connection failed: {e}")

# 3. HuggingFace Space
print("\n--- HuggingFace Space ---")
try:
    r = httpx.get("https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP", timeout=10)
    print(f"  Space page: {r.status_code}")
except Exception as e:
    print(f"  Connection failed: {e}")

# 4. GitHub Repo
print("\n--- GitHub Repo ---")
try:
    r = httpx.get("https://api.github.com/repos/ahmdelbaz28-ux/ETAP-AI-WORK-", timeout=10)
    print(f"  Repo API: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"  Name: {data.get('full_name', '?')}")
        print(f"  Default branch: {data.get('default_branch', '?')}")
        print(f"  Last push: {data.get('pushed_at', '?')}")
except Exception as e:
    print(f"  Connection failed: {e}")

# 5. Vercel
print("\n--- Vercel ---")
try:
    r = httpx.get("https://etap-ai-work.vercel.app", timeout=10)
    print(f"  Live site: {r.status_code}")
except Exception as e:
    print(f"  Connection failed: {e}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
