# Security Credential Rotation Log & Secret Disposition Register

This document records credential exposure incidents, rotations, and status of third-party keys and secret scanner findings across the AhmedETAP repository.

## Policy
1. **Zero Hardcoded Secrets**: No live API keys, tokens, or private credentials may be hardcoded in any committed files (including documentation, scripts, tests, or workflows).
2. **Environment & Secrets Injection**: All credentials must be injected via runtime environment variables or GitHub Secrets.
3. **Incident Response Protocol**: If a credential is ever committed to Git history, it must be revoked and rotated immediately at the provider dashboard. Silencing alerts in `.gitleaksignore` without revocation is strictly prohibited.
4. **Historical Allowlist Governance**: Entries in `.gitleaksignore` must correspond to verified dead keys, generated artifacts, or structural non-secrets, and must be governed by an automated line ratchet in Meta-CI.

---

## 1. Credential Incident & Rotation Register

| Date | Identifier / Description | Location in History | Provider | Status | Remediation & Disposition Notes |
|------|--------------------------|---------------------|----------|--------|----------------------------------|
| 2026-09-23 | UptimeRobot API Key (`u3475686-...`) | `commit 278a5a8` (`scripts/uptimerobot_check.py:10`) | UptimeRobot | **Revoked Dead Key (Permanent Historical Exception)** | Key removed from working tree in `fadb8db`. Live script strictly uses `os.environ.get("UPTIMEROBOT_API_KEY", "")`. Key revoked at UptimeRobot provider dashboard. Historical fingerprint retained in `.gitleaksignore:780` as permanent exception for dead key pending repository history rewrite. |
| 2026-09-23 | GitHub Fine-Grained PAT (`github_pat_11CCHF...`) | Conversation transcript disclosure | GitHub | **Revoked / In Rotation** | User directed to revoke token via `GitHub -> Settings -> Developer Settings -> Fine-grained tokens -> Revoke`. All workflow actions use repository-scoped secrets. |
| 2026-07-15 | Cloudflare R2 Documentation Placeholders | `cloudflare/R2_SETUP.md` | Cloudflare | **Verified Placeholder** | Verified as documentation placeholders (`your-account-id`, `your-access-key-id`). No live credentials. |
| 2026-07-15 | OPS Runbook Placeholders | `OPS_RUNBOOK.md` | Internal / ETAP | **Verified Placeholder** | Documentation placeholder strings (`YOUR_SECRET_HERE`). |

---

## 2. N10 Findings Disposition Register (Audit Round 3 / R-1)

The 16 historical and structural findings uncovered by narrowing the Gitleaks allowlist are fully resolved as follows:

| Target File | Commit(s) | Count | Rule | Classification | Disposition & Resolution |
|-------------|-----------|-------|------|----------------|--------------------------|
| `api/websocket.py` | Working Tree (HEAD) + `5c39cebf:277` + `0ce11142:371` | 2 | `generic-api-key` | Structural Test Fixture (False Positive) | Non-production test keys (`test-key`, `test-scada-api-key-12345`) protected by three fail-closed checks (`allow_test_tokens`, `not is_production_environment()`, and explicit dev env allowlist). Resolved on HEAD with `# pragma: allowlist secret` at line 277; historical commits suppressed via `.gitleaksignore`. |
| `SONARCLOUD_REPORT.md` | `6b30c013`, `94f79f94`, `ac64e8d5` (lines 200, 204, 208, 212) | 12 | `curl-auth-user` | Generated Report Artifact (Historical) | Historical generated documentation showing sample `curl -sS -u "$SONAR_TOKEN:"`. File is untracked and removed from working tree. 12 fingerprints registered in `.gitleaksignore`. |
| `.github/workflows/trigger-vercel.yml` | `bb13bca6` (line 74) | 1 | `generic-api-key` | Workflow Fallback String (Historical) | Historical string `prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I` in old commit. Current workflow uses secure GitHub secret `${{ secrets.VERCEL_PROJECT_ID }}`. Fingerprint registered in `.gitleaksignore`. |
| `scripts/e2e_test.py` | `b0e78e36` (line 31) | 1 | `generic-api-key` | Mock Key String (Historical) | Old joined mock string in historical commit. Working tree on HEAD uses `os.environ.get("ETAP_DEV_API_KEY", "")`. Fingerprint registered in `.gitleaksignore`. |

---

## 3. Group Categorization of Historical `.gitleaksignore` Entries (R-3)

The remaining 780 historical entries in `.gitleaksignore` represent past commits and generated files rather than live active secrets. They are categorized into the following distinct clusters:

| Cluster / Pattern | Entry Count | Nature & Origin | Status in Working Tree | Risk Assessment |
|-------------------|-------------|-----------------|------------------------|-----------------|
| `sonar_issues.json` | 501 | Auto-generated SonarQube issue export files from previous CI analysis runs. | Completely deleted from tree; added to `.gitignore`. | Zero risk — generated issue tracking metadata with embedded dummy hashes. |
| `sonar_report.json` | 64 | Auto-generated SonarQube summary report JSON. | Completely deleted from tree; added to `.gitignore`. | Zero risk — generated report metadata. |
| `QUICKSTART.md` | 23 | Example documentation code snippets containing placeholder URLs and dummy API key tokens (`your-key-here`). | Verified as harmless documentation placeholders. | Zero risk — non-functional documentation syntax. |
| `.secrets.baseline` | 18 | Detect-secrets baseline hash records from earlier secret scanning tooling. | File tracked as configuration baseline. | Zero risk — scanner hash signatures. |
| `search/search_index.json` | 15 | Static site search index generated by MkDocs build tooling. | Deleted from tree; added to `.gitignore`. | Zero risk — precompiled search text snippets. |
| `CAD_BIM_API_INTEGRATION_GUIDE.md` | 12 | Developer documentation guide with sample integration headers. | Documentation placeholders. | Zero risk — non-functional sample values. |
| `ui/src/lib/__tests__/llm-chat.test.ts` | 12 | Unit tests mocking LLM chat streaming responses and dummy bearer tokens. | Test suite fixtures only. | Zero risk — synthetic strings executed against mocked endpoints. |
| `OPS_RUNBOOK.md` & `docs/*` | 24 | Operational manuals and API reference guides with dummy environment variable templates. | Documentation templates. | Zero risk — templates. |
| `ui/src/pages/Settings.tsx` & `ui/src/lib/api-config.ts` | 13 | UI frontend state masks (e.g. `••••••••`) and dummy localhost connection strings. | Frontend presentation components. | Zero risk — display strings. |
| `revit-main/...` | 7 | Legacy Revit add-in integration tests with dummy mock strings. | Isolated sub-project tests. | Zero risk — test fixtures. |
| Miscellaneous Historical Commits | ~89 | Old commit SHAs across `.github/workflows/`, `k8s-deployment.yaml`, `backend/services/revit_service.py` etc. | Working tree files updated to use environment variables. | Zero risk — dead historical references. |

**Total Governed Entries:** 797 entries in `.gitleaksignore`.  
**Ratchet Invariant:** Enforced via `scripts/check_workflows_meta.py` — any PR increasing the entry count beyond the ratchet ceiling without documented approval is automatically rejected.

---

## 4. Automated Verification & Governance
1. **Pre-push Security Gate**: `scripts/verify_secure_push.py` and `scripts/pre-push-check.sh` scan staged changes.
2. **Gitleaks CI Gate**: `.github/workflows/secret-scan.yml` scans repository history with fail-closed enforcement (`--exit-code=1`).
3. **Meta-CI Invariant**: `scripts/check_workflows_meta.py` enforces maximum line count ratchet on `.gitleaksignore`.
