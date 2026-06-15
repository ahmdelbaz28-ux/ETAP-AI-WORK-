# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do NOT open a public GitHub issue** for security vulnerabilities
2. Email security reports to: ahmdelbaz28@gmail.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix released**: Within 30 days for critical issues

### Security Measures

This project implements the following security measures:

| Layer | Controls |
|-------|----------|
| **Authentication** | JWT with bcrypt (cost 14), account lockout (5 attempts), Fernet encryption |
| **Authorization** | RBAC with 5 roles (ADMIN, ENGINEER, ANALYST, VIEWER, GUEST), 25+ permissions |
| **Input Validation** | All endpoints validated with Pydantic v2 / Zod schemas |
| **Code Sandboxing** | Python AST validation, restricted globals, SIGALRM timeout (30s), output truncation (10KB) |
| **Secrets Management** | HashiCorp Vault with encrypted local fallback (Fernet), key rotation, env validation |
| **Rate Limiting** | Token-bucket algorithm with per-client tracking, LRU eviction, TTL cleanup |
| **Audit Logging** | JSON-structured audit trail to `security_audit.log` and `key_access.log` |
| **Dependency Scanning** | Automated via Dependabot + CodeQL |
| **Container Scanning** | Trivy scans for CRITICAL/HIGH vulnerabilities |

### Security Best Practices

- Never commit secrets or API keys
- Use environment variables for configuration
- Enable HTTPS in production
- Rotate API keys regularly
- Review dependency updates

## Standards Compliance

- IEEE 519-2022: Harmonic Control
- IEEE 1584-2018: Arc Flash Hazard Calculations
- IEC 60909: Short-Circuit Currents
- IEC 60255: Protection Relays
- NFPA 70E: Electrical Safety
- OWASP Top 10: Web Application Security
