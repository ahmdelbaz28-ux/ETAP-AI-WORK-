---
title: "AhmedETAP Security Policy & Vulnerability Disclosure"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Core Team"
---

# Security Policy

## Supported Versions

| Version | Supported | Status |
|---|:---:|---|
| **2.1.x** | ✅ Yes | Current Stable Production |
| **2.0.x** | ✅ Yes | Active Maintenance |
| **1.x** | ⚠️ Limited | Security Patches Only |
| **< 1.0** | ❌ No | End of Life |

## Reporting a Vulnerability

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. Email: **ahmdelbaz28@gmail.com**
2. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

| Phase | Timeline |
|-------|----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 1 week |
| Fix released | Within 30 days (critical) |

## Security Measures

> **Secrets Hygiene Notice**: Confirmed by owner (2026-09-21): Rotated all platform credentials as of September 2026 following an internal secrets-hygiene review.

| Layer | Controls |
|-------|----------|
| Authentication | JWT + bcrypt (14 rounds), account lockout (5 attempts) |
| Authorization | RBAC with 5 roles, 25+ permissions |
| Sandboxing | Python AST validation, restricted globals, SIGALRM timeout |
| Secrets | HashiCorp Vault + Fernet encrypted fallback |
| Rate Limiting | Token-bucket with per-client tracking |
| Audit | JSON-structured audit trail with log rotation |
| RASP | SQLi, XSS, Cmdi, SSRF detection |
| MFA | TOTP (RFC 6238) + WebAuthn/FIDO2 |
| Dependencies | CodeQL + Trivy + TruffleHog scanning |

## Security Best Practices

- Never commit secrets or API keys
- Use environment variables for configuration
- Enable HTTPS in production
- Rotate API keys regularly
- Review dependency updates

## Standards Compliance

- OWASP Top 10: Web Application Security
- ISO 27001: Information Security Management
- IEC 62443: Industrial Cybersecurity
- NFPA 70E: Electrical Safety
