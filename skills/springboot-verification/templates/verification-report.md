# Verification Report Template

This template defines the standard output format for the Spring Boot Verification Loop. Use this template when generating verification reports after running the pipeline.

---

## Report Format

```
==========================================
  SPRING BOOT VERIFICATION REPORT
==========================================
Date:       {YYYY-MM-DD HH:MM:SS UTC}
Project:    {project_path}
Build Tool: {maven|gradle}
Threshold:  {coverage_threshold}% coverage

------------------------------------------
Phase Results
------------------------------------------
  Build:      {PASS|FAIL} {detail}
  Static:     {PASS|FAIL} (spotbugs/pmd/checkstyle)
  Tests:      {PASS|FAIL} ({passed}/{total} passed, {coverage}% coverage)
  Security:   {PASS|FAIL} (CVE findings: {n}, secrets: {n})
  Lint:       {PASS|FAIL|SKIP} {detail}
  Diff:       {PASS|FAIL|SKIP} {n} files changed

------------------------------------------
Overall:    {READY|NOT READY}
------------------------------------------

Issues to Fix:
1. {issue_description}
2. {issue_description}
...

Recommendations:
- {recommendation}
- {recommendation}
...

==========================================
```

---

## Detailed Section Templates

### Phase 1: Build

```
BUILD PHASE
-----------
Status:         {PASS|FAIL}
Build Tool:     {maven|gradle}
Command:        {command_executed}
Duration:       {duration_seconds}s

Errors (if FAIL):
  - {error_message}
  - {error_message}
```

### Phase 2: Static Analysis

```
STATIC ANALYSIS PHASE
---------------------
Status:         {PASS|FAIL}

SpotBugs:
  Bugs:         {n} ({n} high, {n} medium, {n} low)
  Status:       {PASS|FAIL}

PMD:
  Violations:   {n} ({n} high, {n} medium, {n} low)
  Status:       {PASS|FAIL}

Checkstyle:
  Violations:   {n} ({n} error, {n} warning)
  Status:       {PASS|FAIL}

Top Violations:
  1. [{severity}] {file}:{line} — {message}
  2. [{severity}] {file}:{line} — {message}
```

### Phase 3: Tests + Coverage

```
TESTS + COVERAGE PHASE
----------------------
Status:         {PASS|FAIL}

Test Summary:
  Total:        {n}
  Passed:       {n}
  Failed:       {n}
  Skipped:      {n}
  Duration:     {duration_seconds}s

Coverage:
  Instructions: {pct}%  ({covered}/{total})
  Lines:        {pct}%  ({covered}/{total})
  Branches:     {pct}%  ({covered}/{total})
  Methods:      {pct}%  ({covered}/{total})

Coverage Threshold: {threshold}%
Coverage Status: {PASS|FAIL}

Failed Tests (if any):
  1. {test_class}.{test_method}
     {failure_message}
  2. {test_class}.{test_method}
     {failure_message}

Per-Class Coverage (if --per-class):
  [PASS] com.example.service.UserService: 95% lines
  [FAIL] com.example.controller.UserController: 62% lines
  [PASS] com.example.repository.UserRepository: 88% lines
```

### Phase 4: Security Scan

```
SECURITY SCAN PHASE
-------------------
Status:         {PASS|FAIL}

OWASP Dependency Check:
  CVE Findings: {n} ({n} critical, {n} high, {n} medium, {n} low)
  Status:       {PASS|FAIL}

  Critical CVEs:
    - CVE-2024-XXXXX: {description} (CVSS: {score})
    - CVE-2024-YYYYY: {description} (CVSS: {score})

Secrets Scan:
  Secrets Found: {n} ({n} critical, {n} warning)
  Status:       {PASS|FAIL}

  Critical Findings:
    - {file}:{line}: {pattern_description}
    - {file}:{line}: {pattern_description}

Security Anti-Patterns:
  System.out.println:      {n} finding(s)
  Raw exception exposure:  {n} finding(s)
  Wildcard CORS:           {n} finding(s)
  CSRF disabled:           {n} finding(s)
```

### Phase 5: Lint/Format

```
LINT/FORMAT PHASE
-----------------
Status:         {PASS|FAIL|SKIP}

Formatter:      {spotless|google-java-format|...}
Files Checked:  {n}
Violations:     {n}

Violations (if any):
  - {file}: {violation_description}
  - {file}: {violation_description}

Fix Command:
  {mvn spotless:apply | ./gradlew spotlessApply}
```

### Phase 6: Diff Review

```
DIFF REVIEW PHASE
-----------------
Status:         {PASS|FAIL|SKIP}

Files Changed:  {n}
  - {file_path} (+{additions}/-{deletions})
  - {file_path} (+{additions}/-{deletions})

Checklist:
  [x] No debugging logs left
  [x] Meaningful errors and HTTP statuses
  [x] Transactions and validation present
  [ ] Config changes documented
  [x] No TODO/FIXME in critical paths

Issues Found:
  - {file}:{line}: {issue_description}
```

---

## JSON Output Format

For programmatic consumption, the report can also be generated in JSON:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "project": "/path/to/project",
  "buildTool": "maven",
  "threshold": 80,
  "phases": {
    "build": {
      "status": "PASS",
      "duration": 12.5
    },
    "static": {
      "status": "FAIL",
      "spotbugs": { "status": "PASS", "bugs": 0 },
      "pmd": { "status": "FAIL", "violations": 3 },
      "checkstyle": { "status": "PASS", "violations": 0 }
    },
    "test": {
      "status": "PASS",
      "total": 45,
      "passed": 45,
      "failed": 0,
      "skipped": 0,
      "coverage": {
        "line": 85.2,
        "branch": 72.1,
        "instruction": 83.7
      }
    },
    "security": {
      "status": "PASS",
      "cveFindings": 0,
      "secretsFound": 0,
      "antiPatterns": 1
    },
    "lint": {
      "status": "PASS",
      "violations": 0
    },
    "diff": {
      "status": "PASS",
      "filesChanged": 3
    }
  },
  "overall": "READY",
  "issues": [],
  "recommendations": [
    "Review 1 PMD violation in UserController.java"
  ]
}
```

---

## Markdown Output Format

For integration with PR comments or documentation:

```markdown
## 🔍 Spring Boot Verification Report

| Phase | Status | Details |
|-------|--------|---------|
| Build | ✅ PASS | Compiled successfully |
| Static | ❌ FAIL | 3 PMD violations |
| Tests | ✅ PASS | 45/45 passed, 85% coverage |
| Security | ✅ PASS | No CVEs, no secrets |
| Lint | ✅ PASS | No formatting issues |
| Diff | ✅ PASS | 3 files changed |

**Overall: ❌ NOT READY**

### Issues to Fix
1. [PMD] UserController.java:45 - Avoid instantiating new objects inside loops
2. [PMD] OrderService.java:112 - Useless parentheses around expression
3. [PMD] UserRepository.java:23 - Short variable name 'id'

### Recommendations
- Fix the 3 PMD violations before merging
- Consider adding branch coverage tests for OrderService
```
