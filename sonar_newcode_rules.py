#!/usr/bin/env python3
import requests
import json

TOKEN = "e0176c608df2d1ea7646f309eca150fd94136d17"
PROJECT = "ahmdelbaz28-ux_ETAP-AI-WORK-"
BASE = "https://sonarcloud.io/api"
headers = {"Authorization": f"Bearer {TOKEN}"}

# New code issues
r = requests.get(f"{BASE}/issues/search", headers=headers, params={"organization": "ahmdelbaz28-ux", "componentKeys": PROJECT, "inNewCodePeriod": "true", "ps": 100})
data = r.json()
new_issues = data.get("issues", [])
print(f"NEW CODE ISSUES TOTAL: {data.get('total', 0)}")
for iss in new_issues[:20]:
    print(f"  [{iss.get('severity')}] [{iss.get('type')}] {iss.get('rule')} - {iss.get('component').replace('ahmdelbaz28-ux_ETAP-AI-WORK-:', '')}:{iss.get('line')} - {iss.get('message')}")

# Get rule descriptions for top rules
top_rules = ["python:S3776", "python:S8415", "python:S8409", "python:S1192", "typescript:S3358", 
             "python:S9073", "python:S5778", "python:S5958", "python:S1066", "typescript:S3776",
             "typescript:S2486", "python:S6353", "typescript:S6478", "python:S6546", "python:S1172"]
print("\n=== RULE DESCRIPTIONS ===")
for rule in top_rules:
    r = requests.get(f"{BASE}/rules/search", headers=headers, params={"rule_key": rule, "ps": 1})
    data = r.json()
    rules = data.get("rules", [])
    if rules:
        r_data = rules[0]
        print(f"\n{rule}:")
        print(f"  Name: {r_data.get('name')}")
        print(f"  Desc: {r_data.get('htmlDesc', r_data.get('mdDesc', 'N/A'))[:200]}")
