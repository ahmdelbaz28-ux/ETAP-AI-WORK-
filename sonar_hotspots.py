#!/usr/bin/env python3
import requests
import json

TOKEN = "e0176c608df2d1ea7646f309eca150fd94136d17"
PROJECT = "ahmdelbaz28-ux_ETAP-AI-WORK-"
BASE = "https://sonarcloud.io/api"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Hotspots
r = requests.get(f"{BASE}/hotspots/search", headers=headers, params={"projectKey": PROJECT, "status": "TO_REVIEW", "ps": 100})
data = r.json()
print("HOTSPOTS TOTAL:", data.get("total", 0))
for h in data.get("hotspots", [])[:20]:
    print(f"  [{h.get('status')}] {h.get('message')} - {h.get('component')}:{h.get('line')} - {h.get('rule')}")

# Duplication metrics
r2 = requests.get(f"{BASE}/measures/component", headers=headers, params={"component": PROJECT, "metricKeys": "duplicated_lines,duplicated_lines_density,duplicated_blocks,duplicated_files"})
data2 = r2.json()
print("\nDUPLICATION METRICS:")
for m in data2.get("component", {}).get("measures", []):
    print(f"  {m['metric']}: {m['value']}")

# Files with most duplication
r3 = requests.get(f"{BASE}/components/tree", headers=headers, params={"component": PROJECT, "qualifiers": "FIL", "metricKeys": "duplicated_lines_density", "s": "metric", "metricSort": "duplicated_lines_density", "asc": "false", "ps": 10})
data3 = r3.json()
print("\nTOP DUPLICATED FILES:")
for comp in data3.get("components", []):
    print(f"  {comp.get('name')}: {comp.get('measures', [{}])[0].get('value', 'N/A')}")
