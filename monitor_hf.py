#!/usr/bin/env python3
"""Monitor HF Space build status."""
import json
import sys
import time
import urllib.request

URL = "https://huggingface.co/api/spaces/ahmdelbaz28/AhmedETAP-Platform"

def get_status():
    req = urllib.request.Request(URL)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)

data = get_status()
rt = data.get("runtime", {})
print(f"Stage: {rt.get('stage')}")
print(f"Hardware: {rt.get('hardware')}")
print(f"SHA: {data.get('sha', '?')[:12]}")
print(f"Error: {str(rt.get('errorMessage', 'N/A'))[:200]}")
print(f"New SHA (a73e925): {data.get('sha', '')[:7]}")

if data.get("sha", "")[:7] == "a73e925":
    print("New commit detected - build should be in progress")
else:
    print(f"Current SHA is {data.get('sha', '')[:7]} - waiting for new commit to be picked up")

print()
print("Polling for build status (max 5 minutes)...")
for i in range(60):
    time.sleep(5)
    try:
        data = get_status()
        stage = data.get("runtime", {}).get("stage", "N/A")
        sha = data.get("sha", "?")[:12]
        print(f"  [{i*5}s] Stage: {stage}, SHA: {sha}")
        if stage == "RUNNING":
            print()
            print("HF Space is RUNNING - build succeeded!")
            sys.exit(0)
        if stage == "BUILD_ERROR":
            print()
            err = data.get("runtime", {}).get("errorMessage", "Unknown error")
            print(f"BUILD_ERROR: {str(err)[:500]}")
            sys.exit(1)
    except Exception as e:
        print(f"  [{i*5}s] Error: {e}")

print("Timeout - build still in progress")
