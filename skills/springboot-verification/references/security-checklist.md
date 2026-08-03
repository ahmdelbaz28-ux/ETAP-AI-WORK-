# Security Checklist for Spring Boot Verification

This checklist covers the security aspects of the Spring Boot Verification Loop, including dependency scanning, secret detection, configuration hardening, and common anti-patterns. Use this as a reference during Phase 4 (Security Scan) and Phase 6 (Diff Review).

---

## Table of Contents

1. [Dependency Vulnerabilities](#1-dependency-vulnerabilities)
2. [Secrets in Source Code](#2-secrets-in-source-code)
3. [Configuration Hardening](#3-configuration-hardening)
4. [Authentication & Authorization](#4-authentication--authorization)
5. [Input Validation](#5-input-validation)
6. [Data Protection](#6-data-protection)
7. [Logging & Monitoring](#7-logging--monitoring)
8. [HTTP Security Headers](#8-http-security-headers)
9. [Database Security](#9-database-security)
10. [API Security](#10-api-security)
11. [Common Anti-Patterns](#11-common-anti-patterns)
12. [Pre-Deployment Checklist](#12-pre-deployment-checklist)

---

## 1. Dependency Vulnerabilities

### Tools

- **OWASP Dependency-Check** — Scans for known CVEs in dependencies
- **Snyk** — Commercial tool with better NVD sync
- **Trivy** — Fast vulnerability scanner for containers and filesystems

### Thresholds

| CVSS Score | Action |
|------------|--------|
| Critical (9.0+) | Block release, fix immediately |
| High (7.0–8.9) | Block release, fix before merge |
| Medium (4.0–6.9) | Review, create ticket, plan fix |
| Low (0.1–3.9) | Review, accept risk with documentation |

### Commands

```bash
# Maven
mvn org.owasp:dependency-check-maven:check

# Gradle
./gradlew dependencyCheckAnalyze

# Trivy (filesystem)
trivy fs --severity HIGH,CRITICAL .

# Trivy (Docker image)
trivy image --severity HIGH,CRITICAL myapp:latest
```

### Common Vulnerable Dependencies

| Library | Known Issues | Fix |
|---------|-------------|-----|
| `log4j-core` < 2.17.0 | Log4Shell (CVE-2021-44228) | Upgrade to 2.17.0+ |
| `jackson-databind` | Deserialization attacks | Keep updated |
| `spring-framework` < 5.3.18 | Spring4Shell (CVE-2022-22965) | Upgrade to 5.3.18+ |
| `snakeyaml` < 1.31 | Deserialization attacks | Upgrade to 2.0+ |

---

## 2. Secrets in Source Code

### What to Scan For

| Pattern | Severity | Example |
|---------|----------|---------|
| Hardcoded passwords | CRITICAL | `password = "mysecret123"` |
| AWS Access Keys | CRITICAL | `AKIAIOSFODNN7EXAMPLE` |
| AWS Secret Keys | CRITICAL | 40-char base64 string |
| OpenAI API Keys | CRITICAL | `sk-proj-...` |
| Stripe Secret Keys | CRITICAL | `sk_live_...` |
| GitHub Tokens | CRITICAL | `ghp_...` |
| JWT Secrets | CRITICAL | `jwt.secret = "..."` |
| Private Keys | CRITICAL | `-----BEGIN RSA PRIVATE KEY-----` |
| API Key patterns | WARNING | `api_key = "..."` |
| Database URLs with credentials | WARNING | `jdbc:postgres://user:pass@host/db` |
| Bearer tokens | WARNING | `Authorization: Bearer ...` |

### Scanning Commands

```bash
# Passwords
grep -rn 'password\s*=\s*"' src/ --include="*.java" --include="*.yml" --include="*.properties"

# Common API key patterns
grep -rn 'sk-\|api_key\|secret' src/ --include="*.java" --include="*.yml"

# AWS keys
grep -rn 'AKIA[0-9A-Z]\{16\}' src/ --include="*.java" --include="*.yml"

# Private keys
grep -rn 'BEGIN.*PRIVATE KEY' src/ --include="*.java" --include="*.yml"

# GitHub tokens
grep -rn 'ghp_[a-zA-Z0-9]\{36\}' src/ --include="*.java" --include="*.yml"

# Git history (if git-secrets is configured)
git secrets --scan
```

### Best Practices

- Use environment variables or Spring Cloud Config for secrets
- Use Vault or AWS Secrets Manager for production secrets
- Add secret patterns to `.gitignore` and pre-commit hooks
- Use `jasypt-spring-boot` for encrypting properties
- Never commit `.env` files to version control

---

## 3. Configuration Hardening

### application.properties / application.yml Checks

```yaml
# ❌ DO NOT
spring.h2.console.enabled=true          # Exposes H2 console
management.endpoints.web.exposure.include=*  # Exposes all actuator endpoints
logging.level.root=DEBUG                # Verbose logging in production
server.ssl.enabled=false                # No TLS in production

# ✅ DO
spring.h2.console.enabled=false
management.endpoints.web.exposure.include=health,info,metrics
logging.level.root=WARN
server.ssl.enabled=true
spring.datasource.password=${DB_PASSWORD}  # Use env variables
```

### Actuator Security

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health, info, metrics, prometheus
  endpoint:
    health:
      show-details: when-authorized
  security:
    enabled: true
```

### Server Configuration

```yaml
server:
  port: 8443
  ssl:
    enabled: true
    key-store: classpath:keystore.p12
    key-store-password: ${SSL_KEYSTORE_PASSWORD}
    key-store-type: PKCS12
  servlet:
    session:
      timeout: 30m
      cookie:
        http-only: true
        secure: true
        same-site: strict
```

---

## 4. Authentication & Authorization

### Security Config Checklist

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()))
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .requestMatchers("/api/**").authenticated()
                .anyRequest().denyAll())
            .headers(headers -> headers
                .contentSecurityPolicy(csp -> csp.policyDirectives("default-src 'self'"))
                .frameOptions(HeadersConfigurer.FrameOptionsConfig::deny)
                .xssProtection(xss -> xss.headerValue(XXssProtectionHeaderWriter.HeaderValue.ENABLED_MODE_BLOCK))
                .httpStrictTransportSecurity(hsts -> hsts
                    .includeSubDomains(true)
                    .maxAgeInSeconds(31536000)));
        return http.build();
    }
}
```

### Anti-Patterns to Avoid

```java
// ❌ Never do this
http.csrf().disable();
http.cors().disable();
http.headers().frameOptions().disable();
http.authorizeRequests().anyRequest().permitAll();

// ❌ Never expose raw exception messages
@ExceptionHandler(Exception.class)
public ResponseEntity<String> handle(Exception e) {
    return ResponseEntity.status(500).body(e.getMessage()); // Leaks internals
}

// ✅ Do this instead
@ExceptionHandler(Exception.class)
public ResponseEntity<ErrorResponse> handle(Exception e) {
    log.error("Unexpected error", e);
    return ResponseEntity.status(500)
        .body(new ErrorResponse("INTERNAL_ERROR", "An unexpected error occurred"));
}
```

---

## 5. Input Validation

### Bean Validation

```java
public record CreateUserDto(
    @NotBlank(message = "Name is required")
    @Size(min = 1, max = 100, message = "Name must be 1-100 characters")
    String name,

    @NotBlank(message = "Email is required")
    @Email(message = "Invalid email format")
    String email
) {}
```

### Controller Validation

```java
@RestController
@RequestMapping("/api/users")
public class UserController {

    @PostMapping
    public ResponseEntity<UserDto> create(
            @Valid @RequestBody CreateUserDto dto,  // @Valid triggers validation
            BindingResult bindingResult) {
        // Spring automatically returns 400 if validation fails
        return ResponseEntity.status(201).body(userService.create(dto));
    }
}
```

### SQL Injection Prevention

```java
// ❌ Never concatenate user input into queries
String query = "SELECT * FROM users WHERE email = '" + email + "'";

// ✅ Always use parameterized queries / Spring Data
@Query("SELECT u FROM User u WHERE u.email = :email")
Optional<User> findByEmail(@Param("email") String email);
```

---

## 6. Data Protection

### Encryption at Rest

```yaml
spring:
  datasource:
    url: jdbc:postgresql://host/db?sslmode=require
  jpa:
    properties:
      hibernate:
        dialect: org.hibernate.dialect.PostgreSQLDialect
```

### Encryption in Transit

```yaml
server:
  ssl:
    enabled: true
    key-store: classpath:keystore.p12
    key-store-password: ${SSL_KEYSTORE_PASSWORD}
```

### Sensitive Data Masking

```java
public record UserDto(
    Long id,
    String name,
    @JsonSerialize(using = MaskedEmailSerializer.class)
    String email
) {}

public class MaskedEmailSerializer extends JsonSerializer<String> {
    @Override
    public void serialize(String value, JsonGenerator gen, SerializerProvider provider)
            throws IOException {
        if (value != null && value.contains("@")) {
            String[] parts = value.split("@");
            String masked = parts[0].substring(0, Math.min(2, parts[0].length())) + "***@" + parts[1];
            gen.writeString(masked);
        } else {
            gen.writeString("***");
        }
    }
}
```

---

## 7. Logging & Monitoring

### Logging Anti-Patterns

```java
// ❌ Never log sensitive data
log.info("User login: password={}", password);
log.info("Credit card: {}", creditCardNumber);

// ❌ Never use System.out.println
System.out.println("Debug: " + userData);

// ✅ Log responsibly
log.info("User login: userId={}", userId);
log.debug("Processing request for userId={}", userId);  // with log level guard
```

### Structured Logging

```yaml
logging:
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n"
  level:
    root: WARN
    com.example: INFO
    org.springframework.security: DEBUG
```

---

## 8. HTTP Security Headers

### Required Headers

| Header | Purpose | Recommended Value |
|--------|---------|-------------------|
| `Strict-Transport-Security` | Force HTTPS | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | Prevent MIME sniffing | `nosniff` |
| `X-Frame-Options` | Prevent clickjacking | `DENY` |
| `X-XSS-Protection` | XSS filter | `1; mode=block` |
| `Content-Security-Policy` | Control resource loading | `default-src 'self'` |
| `Referrer-Policy` | Control referrer info | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | Control browser features | `camera=(), microphone=(), geolocation=()` |

### Spring Security Configuration

```java
http.headers(headers -> headers
    .httpStrictTransportSecurity(hsts -> hsts
        .includeSubDomains(true)
        .maxAgeInSeconds(31536000))
    .contentSecurityPolicy(csp -> csp
        .policyDirectives("default-src 'self'; script-src 'self'; style-src 'self'"))
    .frameOptions(HeadersConfigurer.FrameOptionsConfig::deny)
    .xssProtection(xss -> xss.headerValue(XXssProtectionHeaderWriter.HeaderValue.ENABLED_MODE_BLOCK))
    .contentTypeOptions(Customizer.withDefaults())
);
```

---

## 9. Database Security

### Connection Security

```yaml
spring:
  datasource:
    url: jdbc:postgresql://host/db?sslmode=require&sslrootcert=/path/to/ca.pem
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      connection-timeout: 30000
```

### JPA/Hibernate Security

```yaml
spring:
  jpa:
    properties:
      hibernate:
        session:
          events:
            log: LOG_ERROR  # Don't log session events at DEBUG
    open-in-view: false     # Disable OSIV to prevent lazy loading outside transactions
```

---

## 10. API Security

### Rate Limiting

```java
@Configuration
public class RateLimitConfig {

    @Bean
    public FilterRegistrationBean<RateLimitFilter> rateLimitFilter() {
        FilterRegistrationBean<RateLimitFilter> registration = new FilterRegistrationBean<>();
        registration.setFilter(new RateLimitFilter(100, 60)); // 100 requests per 60 seconds
        registration.addUrlPatterns("/api/*");
        return registration;
    }
}
```

### Request Size Limiting

```yaml
spring:
  servlet:
    multipart:
      max-file-size: 10MB
      max-request-size: 10MB
  codec:
    max-in-memory-size: 1MB
```

---

## 11. Common Anti-Patterns

### Patterns to Detect and Reject

| Pattern | Detection | Severity |
|---------|-----------|----------|
| `System.out.println` | `grep -rn "System\.out\.print" src/main/` | WARNING |
| `e.getMessage()` in responses | `grep -rn "e\.getMessage()" src/main/` | WARNING |
| Wildcard CORS | `grep -rn "allowedOrigins.*\*" src/main/` | CRITICAL |
| CSRF disabled | `grep -rn "csrf.*disable" src/main/` | CRITICAL |
| `permitAll()` | `grep -rn "permitAll()" src/main/` | WARNING |
| H2 console enabled | `grep -rn "h2.console.enabled=true" src/main/` | CRITICAL |
| Actuator fully exposed | `grep -rn "exposure.include=\*" src/main/` | CRITICAL |
| Debug logging in prod | `grep -rn "logging.level.root=DEBUG" src/main/` | WARNING |
| HTTP URLs (not HTTPS) | `grep -rn "http://" src/main/` | WARNING |
| Hardcoded credentials | `grep -rn "password\s*=" src/main/` | CRITICAL |

---

## 12. Pre-Deployment Checklist

Before deploying to staging or production, verify:

- [ ] No CRITICAL or HIGH CVEs in dependencies
- [ ] No hardcoded secrets in source code or configuration
- [ ] All sensitive config uses environment variables
- [ ] CSRF protection enabled (unless stateless API with JWT)
- [ ] CORS configured with specific origins (no wildcards)
- [ ] Security headers configured (HSTS, CSP, X-Frame-Options)
- [ ] Database connections use SSL/TLS
- [ ] Rate limiting configured for public endpoints
- [ ] Request size limits configured
- [ ] Logging does not expose sensitive data
- [ ] Actuator endpoints secured and restricted
- [ ] H2 console disabled in production
- [ ] Debug logging disabled in production
- [ ] Session timeout configured
- [ ] Cookie flags set (HttpOnly, Secure, SameSite)
- [ ] Error responses do not leak internal details
- [ ] SQL injection prevention (parameterized queries)
- [ ] Input validation on all endpoints
- [ ] Authentication required on all non-public endpoints
- [ ] Authorization checks on role-specific endpoints
