#!/usr/bin/env python3
import requests
import json
from collections import defaultdict

TOKEN = "e0176c608df2d1ea7646f309eca150fd94136d17"
PROJECT = "ahmdelbaz28-ux_ETAP-AI-WORK-"
BASE = "https://sonarcloud.io/api"
headers = {"Authorization": f"Bearer {TOKEN}"}

# Load full report
with open("sonar_report.json", "r", encoding="utf-8") as f:
    report = json.load(f)

all_issues = report.get("critical_issues", []) + report.get("high_effort", [])
# Actually the JSON structure has critical_issues and high_effort as lists, but high_effort contains tuples which are not JSON serializable.
# Let me just load the original issues from the API again to be safe, or use the saved data.
# Actually, I'll re-query cleanly and build the report.

all_issues = []
page = 1
ps = 100
while True:
    params = {"componentKeys": PROJECT, "ps": ps, "p": page, "resolved": "false"}
    r = requests.get(f"{BASE}/issues/search", headers=headers, params=params)
    data = r.json()
    issues = data.get("issues", [])
    all_issues.extend(issues)
    total = data.get("total", 0)
    if len(all_issues) >= total or not issues:
        break
    page += 1

by_severity = defaultdict(int)
by_type = defaultdict(int)
by_rule = defaultdict(int)
by_component = defaultdict(int)
by_effort = defaultdict(int)
critical_issues = []
high_effort_issues = []

for issue in all_issues:
    sev = issue.get("severity", "UNKNOWN")
    itype = issue.get("type", "UNKNOWN")
    rule = issue.get("rule", "UNKNOWN")
    comp = issue.get("component", "UNKNOWN")
    effort_str = issue.get("effort", "0min")
    try:
        effort = int(effort_str.replace("min", "").strip())
    except:
        effort = 0
    
    by_severity[sev] += 1
    by_type[itype] += 1
    by_rule[rule] += 1
    by_component[comp] += 1
    by_effort[effort_str] += 1
    
    if sev in ("CRITICAL", "BLOCKER"):
        critical_issues.append(issue)
    if effort >= 30:
        high_effort_issues.append((effort, issue))

# Group critical by file
critical_by_file = defaultdict(list)
for iss in critical_issues:
    critical_by_file[iss.get("component")].append(iss)

print("=" * 80)
print("تقرير تدقيق سونار كلاود - ETAP-AI-WORK-")
print("=" * 80)
print(f"\nإجمالي المشاكل المفتوحة: {len(all_issues)}")
print(f"  • أخطاء (BUG): {by_type.get('BUG', 0)}")
print(f"  • نقاط ضعف أمنية (VULNERABILITY): {by_type.get('VULNERABILITY', 0)}")
print(f"  • روائح كود (CODE_SMELL): {by_type.get('CODE_SMELL', 0)}")

print("\n" + "-" * 80)
print("التوزيع حسب الخطورة:")
print("-" * 80)
for sev in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]:
    count = by_severity.get(sev, 0)
    if count > 0:
        pct = count / len(all_issues) * 100
        print(f"  {sev:10s}: {count:3d} ({pct:5.1f}%)")

print("\n" + "-" * 80)
print("أهم 15 قاعدة مخالفة:")
print("-" * 80)
for rule, count in sorted(by_rule.items(), key=lambda x: -x[1])[:15]:
    print(f"  {rule:30s}: {count:3d}")

print("\n" + "-" * 80)
print("الملفات الأكثر تأثراً (Top 15):")
print("-" * 80)
for comp, count in sorted(by_component.items(), key=lambda x: -x[1])[:15]:
    comp_short = comp.replace("ahmdelbaz28-ux_ETAP-AI-WORK-:", "")
    print(f"  {comp_short:50s}: {count:3d}")

print("\n" + "=" * 80)
print(f"المشاكل الحرجة/القاتلة (CRITICAL/BLOCKER): {len(critical_issues)}")
print("=" * 80)
for file_path, issues in sorted(critical_by_file.items(), key=lambda x: -len(x[1])):
    file_short = file_path.replace("ahmdelbaz28-ux_ETAP-AI-WORK-:", "")
    print(f"\n[FILE] {file_short} ({len(issues)} critical issues)")
    for iss in issues:
        rule = iss.get("rule")
        line = iss.get("line")
        msg = iss.get("message")
        effort = iss.get("effort")
        print(f"   -> Line {line}: [{rule}] {msg} (Effort: {effort})")

print("\n" + "=" * 80)
print(f"مشاكل عالية الجهد (>= 30 دقيقة): {len(high_effort_issues)}")
print("=" * 80)
for effort, iss in sorted(high_effort_issues, reverse=True):
    file_short = iss.get("component", "").replace("ahmdelbaz28-ux_ETAP-AI-WORK-:", "")
    print(f"  {effort}min - {file_short}:{iss.get('line')} - [{iss.get('rule')}] {iss.get('message')}")

# Save summary
with open("sonar_summary.txt", "w", encoding="utf-8") as f:
    f.write(f"Total: {len(all_issues)}\n")
    f.write(f"By Severity: {dict(by_severity)}\n")
    f.write(f"By Type: {dict(by_type)}\n")
    f.write(f"By Rule: {dict(by_rule)}\n")
    f.write(f"By Component: {dict(by_component)}\n")
    f.write(f"Critical Count: {len(critical_issues)}\n")
    f.write(f"High Effort Count: {len(high_effort_issues)}\n")

print("\nتم حفظ الملخص في sonar_summary.txt")
