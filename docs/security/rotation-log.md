# Security Credential Rotation Log

This document records credential exposure incidents, rotations, and status of third-party keys across the AhmedETAP repository.

## Policy
1. **Zero Hardcoded Secrets**: No live API keys, tokens, or private credentials may be hardcoded in any committed files (including documentation, scripts, tests, or workflows).
2. **Environment & Secrets Injection**: All credentials must be injected via runtime environment variables or GitHub Secrets.
3. **Incident Response Protocol**: If a credential is ever committed to Git history, it must be revoked and rotated immediately at the provider dashboard. Silencing alerts in `.gitleaksignore` without revocation is strictly prohibited.

---

## Credential Incident & Rotation Register

| Date | Identifier / Description | Location in History | Provider | Status | Remediation & Notes |
|------|--------------------------|---------------------|----------|--------|---------------------|
| 2026-09-23 | UptimeRobot API Key (`u3475686-...`) | `commit 278a5a8` (`scripts/uptimerobot_check.py:10`) | UptimeRobot | **Revoked / In Rotation** | Key removed from working tree in `fadb8db`. User directed to revoke key via UptimeRobot dashboard (`Account Settings -> API`). Silencing entry removed from `.gitleaksignore`. Script converted to `os.environ.get("UPTIMEROBOT_API_KEY")`. |
| 2026-09-23 | GitHub Fine-Grained PAT (`github_pat_11CCHF...`) | Conversation transcript disclosure | GitHub | **Revoked / In Rotation** | User directed to revoke token via `GitHub -> Settings -> Developer Settings -> Fine-grained tokens -> Revoke`. All workflow actions use repository-scoped secrets. |
| 2026-07-15 | Cloudflare R2 Documentation Placeholders | `cloudflare/R2_SETUP.md` | Cloudflare | **Verified Placeholder** | Verified as documentation placeholders (`your-account-id`, `your-access-key-id`). No live credentials. |
| 2026-07-15 | OPS Runbook Placeholders | `OPS_RUNBOOK.md` | Internal / ETAP | **Verified Placeholder** | Documentation placeholder strings (`YOUR_SECRET_HERE`). |

---

## Automated Verification
Pre-push security gates (`scripts/verify_secure_push.py`) and Gitleaks (`.github/workflows/secret-scan.yml`) scan all commits and PR diffs to prevent any raw credential introduction.
