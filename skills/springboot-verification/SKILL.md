---
name: springboot-verification
description: "Verification loop for Spring Boot projects: build, static analysis, tests with coverage, security scans, and diff review before release or PR."
metadata:
  origin: ECC
---

# Spring Boot Verification Loop

Run before PRs, after major changes, and pre-deploy.

## When to Activate

- Before opening a pull request for a Spring Boot service
- After major refactoring or dependency upgrades
- Pre-deployment verification for staging or production
- Running full build → lint → test → security scan pipeline
- Validating test coverage meets thresholds

## Quick Start

### Automated Pipeline

```bash
# Full verification pipeline
bash scripts/springboot-verify.sh

# Quick mode (build + test + static only)
bash scripts/springboot-verify.sh --quick

# With options
bash scripts/springboot-verify.sh \
  --build-tool maven \
  --coverage-threshold 80 \
  --output verification-report.txt \
  --verbose
```

### Coverage Verification Only

```bash
python3 scripts/verify-coverage.py \
  --threshold 80 \
  --per-class \
  --verbose
```

### Secrets Scanning Only

```bash
# Full scan
bash scripts/scan-secrets.sh --strict --verbose

# Count only (for scripting)
bash scripts/scan-secrets.sh --count-only
```

## Phase 1: Build

```bash
mvn -T 4 clean verify -DskipTests
# or
./gradlew clean assemble -x test
```

If build fails, stop and fix.

## Phase 2: Static Analysis

Maven (common plugins):
```bash
mvn -T 4 spotbugs:check pmd:check checkstyle:check
```

Gradle (if configured):
```bash
./gradlew checkstyleMain pmdMain spotbugsMain
```

> **Reference**: See [references/maven-plugins.md](references/maven-plugins.md) or [references/gradle-plugins.md](references/gradle-plugins.md) for plugin configuration details.

## Phase 3: Tests + Coverage

```bash
mvn -T 4 test
mvn jacoco:report   # verify 80%+ coverage
# or
./gradlew test jacocoTestReport
```

Report:
- Total tests, passed/failed
- Coverage % (lines/branches)

> **Reference**: See [references/test-patterns.md](references/test-patterns.md) for test patterns (unit, integration, API).

### Unit Tests

Test service logic in isolation with mocked dependencies:

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

  @Mock private UserRepository userRepository;
  @InjectMocks private UserService userService;

  @Test
  void createUser_validInput_returnsUser() {
    var dto = new CreateUserDto("Alice", "alice@example.com");
    var expected = new User(1L, "Alice", "alice@example.com");
    when(userRepository.save(any(User.class))).thenReturn(expected);

    var result = userService.create(dto);

    assertThat(result.name()).isEqualTo("Alice");
    verify(userRepository).save(any(User.class));
  }

  @Test
  void createUser_duplicateEmail_throwsException() {
    var dto = new CreateUserDto("Alice", "existing@example.com");
    when(userRepository.existsByEmail(dto.email())).thenReturn(true);

    assertThatThrownBy(() -> userService.create(dto))
        .isInstanceOf(DuplicateEmailException.class);
  }
}
```

### Integration Tests with Testcontainers

Test against a real database instead of H2:

```java
@SpringBootTest
@Testcontainers
class UserRepositoryIntegrationTest {

  @Container
  static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
      .withDatabaseName("testdb");

  @DynamicPropertySource
  static void configureProperties(DynamicPropertyRegistry registry) {
    registry.add("spring.datasource.url", postgres::getJdbcUrl);
    registry.add("spring.datasource.username", postgres::getUsername);
    registry.add("spring.datasource.password", postgres::getPassword);
  }

  @Autowired private UserRepository userRepository;

  @Test
  void findByEmail_existingUser_returnsUser() {
    userRepository.save(new User("Alice", "alice@example.com"));

    var found = userRepository.findByEmail("alice@example.com");

    assertThat(found).isPresent();
    assertThat(found.get().getName()).isEqualTo("Alice");
  }
}
```

### API Tests with MockMvc

Test controller layer with full Spring context:

```java
@WebMvcTest(UserController.class)
class UserControllerTest {

  @Autowired private MockMvc mockMvc;
  @MockBean private UserService userService;

  @Test
  void createUser_validInput_returns201() throws Exception {
    var user = new UserDto(1L, "Alice", "alice@example.com");
    when(userService.create(any())).thenReturn(user);

    mockMvc.perform(post("/api/users")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""
                {"name": "Alice", "email": "alice@example.com"}
                """))
        .andExpect(status().isCreated())
        .andExpect(jsonPath("$.name").value("Alice"));
  }

  @Test
  void createUser_invalidEmail_returns400() throws Exception {
    mockMvc.perform(post("/api/users")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""
                {"name": "Alice", "email": "not-an-email"}
                """))
        .andExpect(status().isBadRequest());
  }
}
```

## Phase 4: Security Scan

```bash
# Dependency CVEs
mvn org.owasp:dependency-check-maven:check
# or
./gradlew dependencyCheckAnalyze

# Secrets in source (automated scan)
bash scripts/scan-secrets.sh --strict

# Manual grep patterns
grep -rn "password\s*=\s*\"" src/ --include="*.java" --include="*.yml" --include="*.properties"
grep -rn "sk-\|api_key\|secret" src/ --include="*.java" --include="*.yml"

# Secrets (git history)
git secrets --scan  # if configured
```

### Common Security Findings

```bash
# Check for System.out.println (use logger instead)
grep -rn "System\.out\.print" src/main/ --include="*.java"

# Check for raw exception messages in responses
grep -rn "e\.getMessage()" src/main/ --include="*.java"

# Check for wildcard CORS
grep -rn "allowedOrigins.*\*" src/main/ --include="*.java"
```

> **Reference**: See [references/security-checklist.md](references/security-checklist.md) for the complete security checklist covering dependencies, secrets, configuration hardening, authentication, input validation, and more.

## Phase 5: Lint/Format (optional gate)

```bash
mvn spotless:apply   # if using Spotless plugin
./gradlew spotlessApply
```

## Phase 6: Diff Review

```bash
git diff --stat
git diff
```

Checklist:
- No debugging logs left (`System.out`, `log.debug` without guards)
- Meaningful errors and HTTP statuses
- Transactions and validation present where needed
- Config changes documented

## Output Template

```
VERIFICATION REPORT
===================
Build:     [PASS/FAIL]
Static:    [PASS/FAIL] (spotbugs/pmd/checkstyle)
Tests:     [PASS/FAIL] (X/Y passed, Z% coverage)
Security:  [PASS/FAIL] (CVE findings: N)
Diff:      [X files changed]

Overall:   [READY / NOT READY]

Issues to Fix:
1. ...
2. ...
```

> **Template**: See [templates/verification-report.md](templates/verification-report.md) for detailed report templates (plain text, JSON, Markdown).

## Continuous Mode

- Re-run phases on significant changes or every 30–60 minutes in long sessions
- Keep a short loop: `mvn -T 4 test` + spotbugs for quick feedback

**Remember**: Fast feedback beats late surprises. Keep the gate strict—treat warnings as defects in production systems.

---

## Skill File Structure

```
springboot-verification/
├── SKILL.md                              ← This file (main instructions)
├── _meta.json                            ← Skill metadata
├── agents/
│   └── verification-agent.md             ← Agent definition & execution plan
├── references/
│   ├── maven-plugins.md                  ← Maven plugin configuration reference
│   ├── gradle-plugins.md                 ← Gradle plugin configuration reference
│   ├── test-patterns.md                  ← Test patterns reference (unit/integration/API)
│   ├── security-checklist.md             ← Comprehensive security checklist
│   ├── SKILL.es.md                       ← Spanish version of SKILL.md
│   ├── SKILL.zh-CN.md                    ← Chinese version of SKILL.md
│   ├── SKILL.tr.md                       ← Turkish version of SKILL.md
│   └── SKILL.ja-JP.md                    ← Japanese version of SKILL.md
├── scripts/
│   ├── springboot-verify.sh              ← Main automation script (6-phase pipeline)
│   ├── verify-coverage.py                ← JaCoCo coverage verification script
│   └── scan-secrets.sh                   ← Secrets & security anti-pattern scanner
└── templates/
    └── verification-report.md            ← Report templates (text, JSON, Markdown)
```
