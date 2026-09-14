#!/usr/bin/env python3
import requests
import json
from collections import defaultdict

TOKEN = "e0176c608df2d1ea7646f309eca150fd94136d17"
PROJECT = "ahmdelbaz28-ux_ETAP-AI-WORK-"
ORG = "ahmdelbaz28"
BASE = "https://sonarcloud.io/api"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Fetch all issues with pagination
all_issues = []
page = 1
ps = 100
while True:
    params = {
        "componentKeys": PROJECT,
        "ps": ps,
        "p": page,
        "resolved": "false"
    }
    r = requests.get(f"{BASE}/issues/search", headers=headers, params=params)
    data = r.json()
    issues = data.get("issues", [])
    all_issues.extend(issues)
    total = data.get("total", 0)
    if len(all_issues) >= total or not issues:
        break
    page += 1

print(f"Total issues fetched: {len(all_issues)}")

# Aggregate
by_severity = defaultdict(int)
by_type = defaultdict(int)
by_rule = defaultdict(int)
by_component = defaultdict(int)
by_severity_type = defaultdict(int)
critical_issues = []
high_effort = []

for issue in all_issues:
    sev = issue.get("severity", "UNKNOWN")
    itype = issue.get("type", "UNKNOWN")
    rule = issue.get("rule", "UNKNOWN")
    comp = issue.get("component", "UNKNOWN")
    
    by_severity[sev] += 1
    by_type[itype] += 1
    by_rule[rule] += 1
    by_component[comp] += 1
    by_severity_type[(sev, itype)] += 1
    
    if sev in ("CRITICAL", "BLOCKER"):
        critical_issues.append(issue)
    
    effort_str = issue.get("effort", "0min")
    try:
        effort = int(effort_str.replace("min", "").replace("h", "").strip())
    except:
        effort = 0
    if effort >= 30:
        high_effort.append((effort, issue))

print("\n=== SEVERITY BREAKDOWN ===")
for k, v in sorted(by_severity.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\n=== TYPE BREAKDOWN ===")
for k, v in sorted(by_type.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")

print("\n=== TOP RULES ===")
for k, v in sorted(by_rule.items(), key=lambda x: -x[1])[:20]:
    print(f"  {k}: {v}")

print("\n=== TOP COMPONENTS ===")
for k, v in sorted(by_component.items(), key=lambda x: -x[1])[:20]:
    print(f"  {k}: {v}")

print(f"\n=== CRITICAL/BLOCKER ISSUES ({len(critical_issues)}) ===")
for iss in critical_issues[:20]:
    print(f"  [{iss.get('severity')}] {iss.get('rule')} - {iss.get('component')}:{iss.get('line')} - {iss.get('message')}")

print(f"\n=== HIGH EFFORT ISSUES (>=30min) ===")
for effort, iss in sorted(high_effort, reverse=True)[:20]:
    print(f"  {effort}min - {iss.get('rule')} - {iss.get('component')}:{iss.get('line')} - {iss.get('message')}")

# Save full report
with open("sonar_report.json", "w", encoding="utf-8") as f:
    json.dump({
        "total": len(all_issues),
        "by_severity": dict(by_severity),
        "by_type": dict(by_type),
        "by_rule": dict(by_rule),
        "by_component": dict(by_component),
        "critical_issues": critical_issues,
        "high_effort": [(e, i) for e, i in high_effort]
    }, f, indent=2, ensure_ascii=False)

print("\nFull report saved to sonar_report.json")
