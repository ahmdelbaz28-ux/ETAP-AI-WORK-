# Technical Debt — AhmedETAP

> **Last Audited:** 2026-06-16
> **Severity Scale:** 🔴 Critical | 🟠 High | 🟡 Medium | 🟢 Low

---

## 🔴 Critical Issues

### 1. Exposed Secrets in Git History
- **File:** `.mcp.json` (was committed with TestSprite API key)
- **Status:** Removed from tracking, but still in git history
- **Action:** Run BFG Repo Cleaner to purge from history
- **Command:** `bfg --delete-files .mcp.json && git reflog expire --expire=now --all && git gc --prune=now --aggressive`

---

## 🟠 High Priority

### 2. Duplicate Load Flow Solver — ✅ **Resolved**
- **Files:** `load_flow/load_flow.py` and ~~`load_flow/load_flow_solver_fixed.py`~~
- **Fix:** Consolidated into single canonical `load_flow/load_flow.py`, removed `load_flow_solver_fixed.py`
- **Resolution Date:** 2026-06-22

### 3. No Token Blacklisting in Production
- **File:** `api/auth.py`
- **Issue:** In-memory blacklist lost on restart; no Redis integration
- **Action:** Implement Redis-backed token blacklist
- **Impact:** Security gap in multi-instance deployments

### 4. Rate Limiting is In-Memory Only
- **File:** `engineering_service.py` (line ~726)
- **Issue:** Rate limit store is per-process; useless with multiple workers
- **Action:** Use Redis-backed rate limiting
- **Impact:** Rate limits ineffective in production

### 5. WebAuthn Fallback is Insecure
- **File:** `security/mfa.py`
- **Issue:** Fallback without `webauthn` package doesn't do cryptographic verification
- **Action:** Always reject WebAuthn auth without the library
- **Impact:** Potential MFA bypass

---

## 🟡 Medium Priority

### 6. Missing `useApi` Hook in Frontend
- **File:** `ui/src/lib/api.ts` uses raw `fetch`
- **Issue:** No centralized API hook with error handling, caching, retry
- **Action:** Create `hooks/useApi.ts` with react-query or SWR
- **Impact:** Inconsistent error handling across pages

### 7. Frontend Package Version is `0.0.0`
- **File:** `ui/package.json`
- **Issue:** Version never bumped from initial scaffold
- **Action:** Set to `1.0.0` to match backend
- **Impact:** Confusing for users checking versions

### 8. Outdated COMPLETION_REPORT.md
- **File:** `COMPLETION_REPORT.md`
- **Issue:** References old completion status; no longer accurate
- **Action:** Update or remove
- **Impact:** Misleading documentation

### 9. No HTTPS Enforcement in Production
- **File:** `nginx.conf`
- **Issue:** HTTPS config commented out; no TLS termination
- **Action:** Uncomment and configure TLS certificates
- **Impact:** Data transmitted in plaintext

### 10. Audit Logs Not Rotated in Production
- **File:** `security/security_framework.py`
- **Issue:** Log rotation added locally but not configured in Docker
- **Action:** Add logrotate config for Docker volumes
- **Impact:** Disk space exhaustion

---

## 🟢 Low Priority

### 11. Dead Code Files
| File | Issue |
|------|-------|
| `fix_eol_strings.py` | Utility script, never imported |
| `run_complete_setup.py` | Setup script, never imported |
| `validation_campaign.py` | May be outdated |

### 12. Missing Test Coverage
- **Area:** `digital_twin/`, `gis_integration/`, `scada_model/`
- **Issue:** No dedicated test files for these modules
- **Action:** Add unit tests

### 13. Inconsistent Error Handling
- **Area:** Some API endpoints use try/except with `pass`, others log properly
- **Action:** Standardize error handling pattern

### 14. No TypeScript Strict Mode
- **File:** `ui/tsconfig.json`
- **Issue:** Strict mode not fully enabled
- **Action:** Enable `strict: true` and fix type errors

### 15. CSS Variable Naming
- **File:** `ui/src/index.css`
- **Issue:** Mix of `--bg-primary` and `--color-brand-500` naming conventions
- **Action:** Standardize naming

---

## Summary

| Severity | Count | Status |
|----------|-------|--------|
| 🔴 Critical | 1 | Needs immediate action |
| 🟠 High | 4 | Should fix before v1.1 |
| 🟡 Medium | 5 | Plan for next sprint |
| 🟢 Low | 5 | Backlog |

**Total Technical Debt Items:** 15
