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
2. Email security reports to: security@etap-platform.com
3. Include:
   - Description of the vulnerability
n   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 1 week
- **Fix released**: Within 30 days for critical issues

### Security Measures

This project implements the following security measures:

- **Authentication**: JWT tokens with secure rotation
- **Authorization**: Role-Based Access Control (RBAC) with 5 roles
- **Input Validation**: All endpoints validated with Pydantic/Zod
- **Code Sandboxing**: Python execution sandboxed
- **Rate Limiting**: Per-user and per-endpoint limits
- **Audit Logging**: Comprehensive audit trail
- **Dependency Scanning**: Automated via Dependabot + CodeQL
- **Container Scanning**: Trivy scans for CRITICAL/HIGH vulnerabilities

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
