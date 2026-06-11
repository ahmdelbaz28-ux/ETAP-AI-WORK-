# SECURITY OPERATIONS MANUAL

## ETAP AI Engineering Platform — Security Operations

**Document ID:** SEC-OPS-001  
**Version:** 1.0  
**Date:** 2026-06-10  
**Classification:** Internal — Confidential  
**Owner:** Security Operations Lead  
**Review Cycle:** Quarterly

---

## 1. SECRET ROTATION POLICY

### 1.1 Scope
All secrets managed by the platform, including:

- `API_KEY_SECRET` (Cloudflare Workers Secret)
- `JWT_SECRET` (stored in Cloudflare Workers Secret)
- `ETAP_WORKER_API_KEY` (if using remote ETAP provider)
- `OPENAI_API_KEY` (if using OpenAI provider)
- `QWEN_API_KEY` (if using Qwen provider)
- `GLM_API_KEY` (if using GLM provider)
- `LANGWATCH_API_KEY` (if using LangWatch observability)
- `ENCRYPTION_KEY` (Fernet encryption key for Secrets Manager)

### 1.2 Rotation Schedule

| Secret Type | Rotation Frequency | Rotation Trigger |
|-------------|-------------------|------------------|
| API_KEY_SECRET | Every 90 days | On suspected exposure, employee departure, or incident |
| JWT_SECRET | Every 90 days | On suspected exposure or token compromise |
| ETAP_WORKER_API_KEY | Every 180 days | On vendor change, contract renewal, or incident |
| LLM Provider Keys | Every 180 days | On provider rotation, cost anomaly, or incident |
| LANGWATCH_API_KEY | Every 180 days | On suspected exposure |
| ENCRYPTION_KEY | Every 365 days | Manual only — requires re-encryption of all stored secrets |

### 1.3 Rotation Procedure

#### API_KEY_SECRET (Cloudflare Workers)
```bash
# 1. Generate new secret
NEW_SECRET=$(openssl rand -hex 32)

# 2. Deploy new secret
wrangler secret put API_KEY_SECRET
# Paste new secret

# 3. Update consuming clients
# - Distribute new key to authorized clients
# - Update CI/CD variables if needed

# 4. Revoke old key after 24-hour grace period
# Old key is automatically overwritten by Cloudflare

# 5. Verify
# Test all authenticated endpoints
```

#### JWT_SECRET (Cloudflare Workers)
```bash
# 1. Generate new secret
NEW_JWT_SECRET=$(openssl rand -hex 32)

# 2. Deploy new secret
wrangler secret put JWT_SECRET

# 3. Immediate effect: all existing sessions invalidated
# Users must re-authenticate

# 4. Update any hardcoded test fixtures
```

### 1.4 Emergency Rotation
If a secret is suspected of being exposed:

1. **Immediate** — Rotate the secret within 15 minutes
2. **Notify** — Security team, platform owner, affected users
3. **Investigate** — Review audit logs for unauthorized access
4. **Document** — Create incident report in INCIDENT_RESPONSE_RUNBOOK.md
5. **Verify** — Confirm all services restored with new secret

---

## 2. API KEY ROTATION POLICY

### 2.1 API Key Lifecycle

```
Create → Distribute → Monitor → Rotate → Revoke → Audit
```

### 2.2 Key Creation
- All keys generated via `cryptographically-secure random` (32-byte hex)
- Keys are hashed with bcrypt before comparison (if stored locally)
- Cloudflare Workers uses `wrangler secret put` (encrypted at rest)

### 2.3 Key Monitoring
- Track key usage via `/api/v1/metrics` endpoint
- Alert on anomalous usage patterns (spikes, off-hours access)
- Log every authenticated request via audit logging

### 2.4 Key Revocation
- Immediate revocation via `wrangler secret put` with a new value
- Old sessions invalidate automatically
- No grace period for suspected compromise

### 2.5 API Key Best Practices
- Never commit API keys to source control
- Never log API keys in plaintext
- Use environment-specific keys (dev/staging/prod)
- Rotate keys when team members leave
- Use minimal-scope keys where possible

---

## 3. JWT ROTATION STRATEGY

### 3.1 JWT Token Policy

| Parameter | Value |
|-----------|-------|
| Algorithm | HS256 |
| Token Lifetime | 24 hours (access token) |
| Refresh Token Lifetime | 7 days |
| Issuer | `etap-ai-platform` |
| Audience | `etap-ai-api` |

### 3.2 JWT Secret Rotation
- Rotation invalidates ALL active sessions
- Users must re-authenticate
- Planned rotation: 48-hour advance notice
- Emergency rotation: immediate

### 3.3 Token Validation
- Verify `iss`, `aud`, `exp`, `iat` claims
- Reject tokens with `exp` within 5 minutes of current time
- Log all validation failures via audit logging

### 3.4 Token Storage
- Never store tokens in localStorage (use httpOnly cookies)
- Cloudflare Workers uses encrypted headers
- Test tokens (in test suites) must be ephemeral and never committed

---

## 4. RBAC AUDIT PROCESS

### 4.1 Role Definitions

| Role | Permissions | Typical Users |
|------|-------------|-------------|
| `ADMIN` | Full access, user management, system config | Platform admins |
| `ENGINEER` | Create studies, run ETAP, view reports | Power system engineers |
| `VIEWER` | Read-only access to reports and dashboards | Managers, clients |
| `OPERATOR` | Monitor system, view metrics, no study creation | NOC staff |

### 4.2 RBAC Audit Schedule

| Audit Type | Frequency | Responsible |
|------------|-----------|-------------|
| User Access Review | Monthly | Security Operations |
| Role Assignment Review | Quarterly | Platform Owner |
| Permission Granularity Review | Annually | Security Architect |
| Privileged Access Review | Monthly | Security Operations |

### 4.3 RBAC Audit Procedure

1. **Export** current user list and role assignments
2. **Review** each user for continued need of assigned role
3. **Identify** dormant accounts (no login for 90 days)
4. **Verify** least-privilege principle is followed
5. **Document** findings in quarterly audit report
6. **Remediate** any over-privileged access within 7 days

### 4.4 User Offboarding

1. **Immediate** — Disable account in identity provider
2. **Within 1 hour** — Invalidate all active sessions/JWTs
3. **Within 24 hours** — Remove from RBAC system
4. **Within 7 days** — Archive audit logs for that user

---

## 5. ACCESS REVIEW PROCESS

### 5.1 Review Matrix

| System / Resource | Review Frequency | Reviewer |
|-------------------|------------------|----------|
| Cloudflare Workers Dashboard | Quarterly | Cloud Architect |
| Cloudflare KV Namespaces | Quarterly | Cloud Architect |
| API Keys (wrangler secrets) | Quarterly | Security Operations |
| LLM Provider Accounts | Quarterly | AI Infrastructure |
| ETAP Integration Access | Quarterly | ETAP Architect |
| GitHub Repository | Quarterly | DevOps Lead |
| LangWatch Dashboard | Quarterly | Observability Lead |

### 5.2 Access Review Workflow

```
1. Generate access report
2. Notify reviewers
3. Reviewer validates each access
4. Remove unnecessary access
5. Document exceptions
6. Report to Security Operations
7. Track remediation in risk register
```

---

## 6. SECURITY EVENT LOGGING

### 6.1 Logged Events

| Event | Severity | Retention |
|-------|----------|-----------|
| Authentication success | INFO | 90 days |
| Authentication failure | WARNING | 90 days |
| Rate limit triggered | WARNING | 90 days |
| API key rotation | INFO | 365 days |
| JWT secret rotation | INFO | 365 days |
| Privileged action (admin) | INFO | 365 days |
| Unauthorized access attempt | ERROR | 365 days |
| Secret exposure detected | CRITICAL | Permanent |

### 6.2 Log Format
All security events are logged via the audit logging system:

```json
{
  "timestamp": "2026-06-10T12:00:00Z",
  "event": "AUTH_FAILURE",
  "severity": "WARNING",
  "source_ip": "192.0.2.1",
  "user_agent": "Mozilla/5.0...",
  "path": "/api/v1/studies/run",
  "method": "POST",
  "details": "Invalid API key"
}
```

### 6.3 Log Retention
- Cloudflare KV: 90 days TTL on audit entries
- Exported logs: 365 days in secure storage
- Security incidents: Permanent retention

---

## 7. SECURITY OPERATIONS RUNBOOK

### 7.1 Daily Tasks
- [ ] Review `/api/v1/metrics` for anomaly detection
- [ ] Check `/api/v1/audit/logs` for authentication failures
- [ ] Verify Cloudflare Workers dashboard shows healthy status

### 7.2 Weekly Tasks
- [ ] Review failed authentication trends
- [ ] Check rate limit hit patterns
- [ ] Verify backup scripts executed successfully

### 7.3 Monthly Tasks
- [ ] RBAC user access review
- [ ] Secret rotation readiness check
- [ ] Security patch status review
- [ ] Vulnerability scan (if applicable)

### 7.4 Quarterly Tasks
- [ ] Full secret rotation (or per schedule)
- [ ] Access review for all systems
- [ ] Security operations manual review
- [ ] Incident response drill
- [ ] Disaster recovery test

---

## 8. INCIDENT ESCALATION

### 8.1 Security Incident Severity

| Severity | Examples | Response Time |
|----------|----------|---------------|
| SEV-1 | Secret exposure, unauthorized admin access | 15 minutes |
| SEV-2 | Suspicious API usage, repeated auth failures | 1 hour |
| SEV-3 | Individual account compromise, policy violation | 4 hours |
| SEV-4 | Minor access anomaly, documentation gap | 24 hours |

### 8.2 Escalation Path

```
Detection → SRE On-Call → Security Operations → Platform Owner → CTO
  SEV-1:      5 min         15 min              30 min          1 hour
  SEV-2:      15 min        1 hour              4 hours         24 hours
  SEV-3:      1 hour        4 hours             24 hours        48 hours
  SEV-4:      24 hours      48 hours            72 hours        1 week
```

---

## 9. COMPLIANCE MAPPINGS

### 9.1 SOC 2 Type II
- AC-1: Access Control → RBAC Audit Process
- AC-2: Logical Access → Secret Rotation Policy
- AC-3: Access Removal → User Offboarding
- AU-1: Audit Logging → Security Event Logging
- CM-1: Change Management → Secret Rotation Procedure

### 9.2 ISO 27001
- A.9.1: Access Control Policy → RBAC definitions
- A.9.2: User Access Management → Access Review Process
- A.9.4: System Access Control → API Key Rotation
- A.12.4: Logging and Monitoring → Audit Logging
- A.12.6: Vulnerability Management → Quarterly review

### 9.3 NERC CIP (for utilities)
- CIP-003: Security Management → Security Operations Manual
- CIP-004: Personnel & Training → RBAC + Access Review
- CIP-005: Electronic Security → API Key + JWT policies
- CIP-007: System Management → Secret Rotation
- CIP-011: Information Protection → Encryption key management

---

## 10. APPENDICES

### Appendix A: Secret Rotation Checklist

```
[ ] Identify secret to rotate
[ ] Generate new cryptographically random secret
[ ] Update secret in Cloudflare Workers (wrangler secret put)
[ ] Update any CI/CD environment variables
[ ] Notify affected users if session invalidation occurs
[ ] Test all dependent services
[ ] Update secret registry documentation
[ ] Verify old secret is no longer functional
[ ] Document rotation in audit log
[ ] Close rotation ticket
```

### Appendix B: RBAC Audit Checklist

```
[ ] Export current user-role assignments
[ ] Review each assignment for business justification
[ ] Identify dormant accounts (90+ days no login)
[ ] Identify over-privileged users
[ ] Document findings
[ ] Create remediation tickets
[ ] Track remediation completion
[ ] Report to Security Operations
```

### Appendix C: Security Contact Matrix

| Role | Contact | Escalation |
|------|---------|------------|
| Security Operations Lead | secops@company.com | Platform Owner |
| Platform Owner | platform@company.com | CTO |
| Cloud Architect | cloud@company.com | Platform Owner |
| DevOps Lead | devops@company.com | Platform Owner |
| ETAP Architect | etap@company.com | Platform Owner |

---

**Document Control:**
- Approved by: _________________
- Date: _________________
- Next Review: _________________
