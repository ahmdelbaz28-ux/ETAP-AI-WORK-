# Verification Agent

The verification agent is responsible for executing the Spring Boot Verification Loop on a project. It runs a structured 6-phase pipeline and produces a verification report.

---

## Agent Identity

| Field | Value |
|-------|-------|
| **Name** | `springboot-verification` |
| **Role** | Quality Gate Agent |
| **Trigger** | Before PRs, after major changes, pre-deploy |
| **Scope** | Spring Boot services (Maven or Gradle) |

---

## Activation Conditions

The verification agent activates when any of the following conditions are met:

1. **Pre-PR** — User is about to open a pull request for a Spring Boot service
2. **Post-refactor** — After major refactoring or dependency upgrades
3. **Pre-deploy** — Before deploying to staging or production
4. **On-demand** — User explicitly requests verification
5. **Continuous** — Re-run every 30–60 minutes during long development sessions

---

## Phase Execution Plan

### Phase 1: Build

**Objective**: Verify the project compiles and packages without errors.

**Actions**:
1. Detect build tool (Maven or Gradle)
2. Run clean build with tests skipped
3. If build fails → STOP and report compilation errors
4. If build succeeds → proceed to Phase 2

**Commands**:
```bash
# Maven
mvn -T 4 clean verify -DskipTests

# Gradle
./gradlew clean assemble -x test
```

**Failure Action**: Stop pipeline. Report compilation errors. Do not proceed to subsequent phases.

---

### Phase 2: Static Analysis

**Objective**: Detect code quality issues, bugs, and style violations.

**Actions**:
1. Run SpotBugs for bytecode-level bug detection
2. Run PMD for source-level code quality issues
3. Run Checkstyle for code style compliance
4. Collect and categorize findings by severity

**Commands**:
```bash
# Maven
mvn -T 4 spotbugs:check pmd:check checkstyle:check

# Gradle
./gradlew checkstyleMain pmdMain spotbugsMain
```

**Failure Action**: Report violations. Do not block if only warnings (configurable). Block on errors.

**Reference**: See `references/maven-plugins.md` or `references/gradle-plugins.md` for plugin configuration.

---

### Phase 3: Tests + Coverage

**Objective**: Run all tests and verify coverage meets the configured threshold.

**Actions**:
1. Run all unit tests
2. Run all integration tests
3. Generate JaCoCo coverage report
4. Parse coverage data and verify against threshold (default: 80%)
5. Report: total tests, passed/failed, coverage percentage

**Commands**:
```bash
# Maven
mvn -T 4 test
mvn jacoco:report

# Gradle
./gradlew test jacocoTestReport
```

**Coverage Verification**:
```bash
# Using the verify-coverage.py script
python3 scripts/verify-coverage.py --threshold 80 --per-class
```

**Failure Action**: Report test failures and coverage gaps. Do not proceed if critical tests fail.

**Reference**: See `references/test-patterns.md` for test patterns and best practices.

---

### Phase 4: Security Scan

**Objective**: Detect known vulnerabilities and security anti-patterns.

**Actions**:
1. Run OWASP Dependency-Check for CVE scanning
2. Scan source code for hardcoded secrets
3. Check for common security anti-patterns
4. Categorize findings by severity (CRITICAL/WARNING)

**Commands**:
```bash
# CVE scanning
mvn org.owasp:dependency-check-maven:check
# or
./gradlew dependencyCheckAnalyze

# Secrets scanning
bash scripts/scan-secrets.sh --strict
```

**Failure Action**: Block on CRITICAL findings. Report WARNING findings for review.

**Reference**: See `references/security-checklist.md` for the complete security checklist.

---

### Phase 5: Lint/Format

**Objective**: Ensure code formatting is consistent.

**Actions**:
1. Run Spotless check (or equivalent formatter)
2. Report formatting violations
3. Optionally auto-fix with `spotless:apply`

**Commands**:
```bash
# Maven
mvn spotless:check

# Gradle
./gradlew spotlessCheck
```

**Failure Action**: Report formatting issues. This is an optional gate — can be configured to warn only.

---

### Phase 6: Diff Review

**Objective**: Review the changes for common issues before merge.

**Actions**:
1. Show git diff statistics
2. Check for debugging logs left in code
3. Check for TODO/FIXME markers
4. Verify meaningful errors and HTTP statuses
5. Verify transactions and validation present where needed
6. Verify config changes documented

**Commands**:
```bash
git diff --stat
git diff
```

**Checklist**:
- [ ] No debugging logs left (`System.out`, `log.debug` without guards)
- [ ] Meaningful errors and HTTP statuses
- [ ] Transactions and validation present where needed
- [ ] Config changes documented
- [ ] No TODO/FIXME markers in critical paths
- [ ] No temporary files committed

**Failure Action**: Report findings. Do not block unless critical issues found.

---

## Output Template

After all phases complete, the agent produces a verification report:

```
VERIFICATION REPORT
===================
Date:       <timestamp>
Project:    <project path>
Build Tool: <maven|gradle>
Threshold:  <coverage>%

Build:      [PASS/FAIL]
Static:     [PASS/FAIL] (spotbugs/pmd/checkstyle)
Tests:      [PASS/FAIL] (<passed>/<total> passed, <coverage>% coverage)
Security:   [PASS/FAIL] (CVE findings: <n>, secrets: <n>)
Lint:       [PASS/FAIL/SKIP]
Diff:       [<n> files changed]

Overall:    [READY / NOT READY]

Issues to Fix:
1. <issue description>
2. <issue description>
...

Recommendations:
- <recommendation>
- <recommendation>
```

---

## Continuous Mode

During long development sessions, the agent can operate in continuous mode:

- **Short loop**: `mvn -T 4 test` + SpotBugs for quick feedback
- **Full loop**: Re-run all phases on significant changes
- **Interval**: Every 30–60 minutes in long sessions
- **Trigger**: File changes in `src/main/` or `src/test/`

---

## Quick Mode

For rapid feedback during development, use the quick mode:

```bash
# Only build + test + static analysis
bash scripts/springboot-verify.sh --quick
```

---

## Integration with CI/CD

The verification agent can be integrated into CI/CD pipelines:

### GitHub Actions

```yaml
name: Spring Boot Verification
on: [push, pull_request]
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'
      - name: Run Verification
        run: bash scripts/springboot-verify.sh --output verification-report.txt
      - name: Upload Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: verification-report
          path: verification-report.txt
```

### GitLab CI

```yaml
springboot-verify:
  stage: test
  image: eclipse-temurin:21-jdk
  script:
    - bash scripts/springboot-verify.sh --output verification-report.txt
  artifacts:
    when: always
    paths:
      - verification-report.txt
```

---

## Error Handling

| Scenario | Action |
|----------|--------|
| Build tool not found | Report error, suggest installing Maven or Gradle |
| No JaCoCo report | Report error, suggest running tests with coverage first |
| No git repository | Skip diff review phase, report warning |
| SpotBugs/PMD not configured | Skip static analysis, report warning |
| OWASP not configured | Skip CVE scan, report warning |
| Docker not available | Skip Testcontainers integration tests, report warning |
| Coverage below threshold | Report as FAIL, suggest adding more tests |
| Secrets found | Report as CRITICAL, list affected files |

---

## Decision Matrix

| Phase | PASS | FAIL | SKIP |
|-------|------|------|------|
| Build | Proceed | **STOP** | N/A |
| Static | Proceed | Proceed with warning | If not configured |
| Test | Proceed | **STOP** if critical failures | If no tests |
| Security | Proceed | **STOP** if CRITICAL | If not configured |
| Lint | Proceed | Proceed with warning | If not configured |
| Diff | Proceed | Proceed with warning | If no git |

**Overall**: READY only if all non-skipped phases PASS. NOT READY if any phase FAILs.
