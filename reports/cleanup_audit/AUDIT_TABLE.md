# Root Directory Cleanup Audit Table

## Overview
This audit table documents the categorization, reference verification, action taken, and risk evaluation for files examined during the root directory decluttering process (reducing root from ~350 files to <80 non-dot entries).

| Path | Type | Referenced By (code/import/docker/ci)? | Action | Risk | Evidence / Justification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AI_AGENT_INDEX.md` | generated | None (standalone report) | move to `docs/generated/` | Low | Unreferenced generated audit index. |
| `ARCHITECTURE_DECISIONS.md` | generated | None | move to `docs/generated/` | Low | Architecture notes safely archived in `docs/generated/`. |
| `AUDIT_CORRECTED_REPORT.md` | generated | None | move to `docs/generated/` | Low | Past cycle audit report. |
| `CAD_BIM_API_INTEGRATION_GUIDE.md` | generated | None | move to `docs/generated/` | Low | Specialized integration guide preserved in `docs/generated/`. |
| `CLEANUP_REPORT.md` | generated | None | move to `docs/generated/` | Low | Previous cleanup summary. |
| `COMPREHENSIVE_IMPLEMENTATION_SUMMARY.md` | generated | None | move to `docs/generated/` | Low | Generated implementation summary. |
| `COVERAGE_REPORT.md` | generated | None | move to `docs/generated/` | Low | Historic coverage artifact. |
| `ELECTRON_SECURITY_REPORT.md` | generated | None | move to `docs/generated/` | Low | Security scan summary. |
| `EMAIL_INTEGRATION_README.md` | generated | None | move to `docs/generated/` | Low | Legacy email setup notes. |
| `EXHAUSTIVE_AUDIT_REPORT.md` | generated | None | move to `docs/generated/` | Low | Previous audit artifact. |
| `FINAL_ARTIFACT_MANIFEST.md` | generated | None | move to `docs/generated/` | Low | Artifact manifest archived. |
| `FINAL_COMPREHENSIVE_AUDIT_REPORT.md` | generated | None | move to `docs/generated/` | Low | Previous comprehensive audit. |
| `FINAL_DEPLOYMENT_GUIDE.md` | generated | None | move to `docs/generated/` | Low | Deployment guide copy. |
| `FINAL_RELEASE_CERTIFICATE.md` | generated | None | move to `docs/generated/` | Low | Release certificate copy. |
| `GOVERNANCE_PROPOSALS.md` | generated | None | move to `docs/generated/` | Low | Governance notes. |
| `MCP_SETUP.md` | generated | None | move to `docs/generated/` | Low | Setup notes. |
| `MCP_SETUP_GUIDE.md` | generated | None | move to `docs/generated/` | Low | Setup guide copy. |
| `MULTI_DATABASE_INSTRUCTIONS.md` | generated | None | move to `docs/generated/` | Low | Multi-DB instructions copy. |
| `MULTI_DATABASE_SETUP.md` | generated | None | move to `docs/generated/` | Low | Setup instructions. |
| `OPERATOR_ACTION_ITEMS.md` | generated | None | move to `docs/generated/` | Low | Operator notes. |
| `PHASE2_COVERAGE_REPORT.md` | generated | None | move to `docs/generated/` | Low | Historic phase 2 coverage. |
| `PRE_LAUNCH_CHECKLIST_TRACKER.md` | generated | None | move to `docs/generated/` | Low | Pre-launch tracker. |
| `PRE_LAUNCH_INDEX.md` | generated | None | move to `docs/generated/` | Low | Index of pre-launch docs. |
| `PRE_LAUNCH_REMEDIATION_PLAN.md` | generated | None | move to `docs/generated/` | Low | Remediation plan copy. |
| `QUICK_START_REMEDIATION.md` | generated | None | move to `docs/generated/` | Low | Remediation guide copy. |
| `README_MODERNIZATION_REPORT.md` | generated | None | move to `docs/generated/` | Low | Modernization report copy. |
| `REMEDIATION_PLAN.md` | generated | None | move to `docs/generated/` | Low | Plan document. |
| `REVIT_INTEGRATION_GUIDE.md` | generated | None | move to `docs/generated/` | Low | Revit guide. |
| `SECURITY_CHECKLIST.md` | generated | None | move to `docs/generated/` | Low | Security checklist copy. |
| `SECURITY_COMPLIANCE_SUMMARY.md` | generated | None | move to `docs/generated/` | Low | Security compliance copy. |
| `SECURITY_EXCEPTIONS.md` | generated | None | move to `docs/generated/` | Low | Exceptions log. |
| `SECURITY_FIXES.md` | generated | None | move to `docs/generated/` | Low | Fixes summary. |
| `SECURITY_REMEDIATION_REPORT.md` | generated | None | move to `docs/generated/` | Low | Remediation report. |
| `SECURITY_REQUIREMENTS.md` | generated | None | move to `docs/generated/` | Low | Security requirements copy. |
| `SONARCLOUD_REPORT.md` | generated | None | move to `docs/generated/` | Low | SonarCloud summary report. |
| `STRESS_TEST_REMEDIATION_REPORT.md` | generated | None | move to `docs/generated/` | Low | Stress test findings. |
| `TESTING_SOLUTION_SUMMARY.md` | generated | None | move to `docs/generated/` | Low | Testing summary report. |
| `TEST_REPORT.md` | generated | None | move to `docs/generated/` | Low | Historic test report. |
| `TODO.md` | generated | None | move to `docs/generated/` | Low | Old TODO list. |
| `TODO_phase4_security.md` | generated | None | move to `docs/generated/` | Low | Old phase 4 TODO list. |
| `UI_UX_LOGIN_PAGE_PLAN.md` | generated | None | move to `docs/generated/` | Low | UI design plan copy. |
| `USER_GUIDE_SUMMARY.md` | generated | None | move to `docs/generated/` | Low | User guide summary. |
| `VERCEL_FINAL_REPORT.md` | generated | None | move to `docs/generated/` | Low | Vercel deployment report. |
| `WINDOWS_RELEASE_REPORT.md` | generated | None | move to `docs/generated/` | Low | Windows release report. |
| `ai_agent_instructions.md` | generated | None | move to `docs/generated/` | Low | Agent instructions copy. |
| `ai_quick_reference.md` | generated | None | move to `docs/generated/` | Low | Quick reference copy. |
| `ai_system_prompt.md` | generated | None | move to `docs/generated/` | Low | Prompt notes copy. |
| `forensic_gate_report.md` | generated | None | move to `docs/generated/` | Low | Forensic audit report. |
| `post-merge-certification.md` | generated | None | move to `docs/generated/` | Low | Post-merge cert copy. |
| `scada_etap_gis_integration_guide.md` | generated | None | move to `docs/generated/` | Low | Integration guide copy. |
| `scada_integration_instructions.md` | generated | None | move to `docs/generated/` | Low | SCADA instructions copy. |
| `worklog_entry.md` | generated | None | move to `docs/generated/` | Low | Worklog scratch entry. |
| `style.css` | static | None | move to `docs/static/` | Low | Web asset. |
| `script.js` | static | None | move to `docs/static/` | Low | Web asset. |
| `sitemap.xml` | static | None | move to `docs/static/` | Low | Web asset. |
| `sitemap.xml.gz` | static | None | move to `docs/static/` | Low | Web asset. |
| `API_Test_Collection.postman_collection.json` | generated | None | move to `reports/` | Low | Postman collection report. |
| `FINAL_COMPLETION_REPORT.md` | generated | None | move to `reports/` | Low | Audit completion report. |
| `HTTP_STRESS_TEST_RESULTS.json` | generated | None | move to `reports/` | Low | Stress test output. |
| `NOSONAR_AUDIT.md` | generated | None | move to `reports/` | Low | Sonar audit report. |
| `STATIC_ANALYSIS_REPORT.md` | generated | None | move to `reports/` | Low | Static analysis report. |
| `STRESS_TEST_RESULTS.json` | generated | None | move to `reports/` | Low | Stress test output. |
| `STRICT_STRESS_V3_RESULTS.json` | generated | None | move to `reports/` | Low | Strict stress test output. |
| `VERCEL_VERIFICATION_REPORT.md` | generated | None | move to `reports/` | Low | Vercel report. |
| `arcgis_pro_sdk_repositories_analysis.json` | generated | None | move to `reports/` | Low | SDK repo analysis. |
| `mcp_server_intelligent_index_system.json` | generated | None | move to `reports/` | Low | Index output. |
| `qgis_complete_documentation_index.json` | generated | None | move to `reports/` | Low | Documentation index. |
| `qgis_comprehensive_documentation_index.json` | generated | None | move to `reports/` | Low | Documentation index. |
| `qgis_server_documentation_index.json` | generated | None | move to `reports/` | Low | Documentation index. |
| `qgis_user_manual_index.json` | generated | None | move to `reports/` | Low | Documentation index. |
| `sonar_fix_plan.json` | generated | None | move to `reports/` | Low | Sonar plan artifact. |
| `test_results.json` | generated | None | move to `reports/` | Low | Test run output. |
| `_fitz_compat.py` | script | None | move to `scripts/` | Low | PyMuPDF compatibility shim. |
| `_set_sonar_secret.py` | script | None | move to `scripts/` | Low | One-off config script. |
| `add_prometheus_metrics.py` | script | None | move to `scripts/` | Low | Metric setup script. |
| `apply_engineering_patch.py` | script | None | move to `scripts/` | Low | Patch utility. |
| `arcgis_pro_documentation_index.json` | data | `scripts/arcgis_pro_indexing_workflow.py` | move to `scripts/` | Low | Moved alongside the indexing workflow. |
| `arcgis_pro_indexing_workflow.json` | config | `scripts/arcgis_pro_indexing_workflow.py` | move to `scripts/` | Low | Moved alongside workflow. |
| `arcgis_pro_indexing_workflow.py` | script | None | move to `scripts/` | Low | Indexing utility. |
| `check_hf_status.py` | script | None | move to `scripts/` | Low | HF status checker. |
| `check_results.py` | script | None | move to `scripts/` | Low | Test checker utility. |
| `create_alerts.py` | script | None | move to `scripts/` | Low | Alert generator script. |
| `create_extra_metrics.py` | script | None | move to `scripts/` | Low | Metric script. |
| `final_agent_verification.py` | script | None | move to `scripts/` | Low | Agent verification utility. |
| `fix_agent_structures.py` | script | None | move to `scripts/` | Low | Agent maintenance script. |
| `fix_eol_strings.py` | script | None | move to `scripts/` | Low | EOL string fixer utility. |
| `fix_future_imports.py` | duplicate | Identical upgraded version in `scripts/` | delete | Low | Already exists as `scripts/fix_future_imports.py`. |
| `merge_all_remote_branches.ps1` | script | None | move to `scripts/` | Low | Git helper script. |
| `modify_scada.py` | script | None | move to `scripts/` | Low | SCADA script. |
| `monitor_hf.py` | script | None | move to `scripts/` | Low | HF monitor script. |
| `postman_login.py` | script | None | move to `scripts/` | Low | Auth testing helper. |
| `quickstart.ps1` | script | None | move to `scripts/` | Low | Quickstart PowerShell script. |
| `quickstart.sh` | script | None | move to `scripts/` | Low | Quickstart shell script. |
| `run_arcgis_workflow.ps1` | script | None | move to `scripts/` | Low | Workflow launcher. |
| `run_button_tests.bat` | script | None | move to `scripts/` | Low | Batch test runner. |
| `run_complete_setup.py` | script | None | move to `scripts/` | Low | Setup runner. |
| `run_comprehensive_tests.bat` | script | None | move to `scripts/` | Low | Batch runner. |
| `run_cov.bat` | script | None | move to `scripts/` | Low | Coverage batch runner. |
| `run_git.py` | script | None | move to `scripts/` | Low | Git runner utility. |
| `scada_etap_consumer.py` | script | None | move to `scripts/` | Low | SCADA consumer demo. |
| `setup_and_run_tests.bat` | script | None | move to `scripts/` | Low | Setup test batch. |
| `setup_and_run_tests.sh` | script | None | move to `scripts/` | Low | Setup shell runner. |
| `start_worker.py` | script | None | move to `scripts/` | Low | Worker entry script. |
| `sync.ps1` | script | None | move to `scripts/` | Low | Sync PowerShell. |
| `sync_hf.py` | script | None | move to `scripts/` | Low | HF space sync script. |
| `sync_v2.ps1` | script | None | move to `scripts/` | Low | Sync helper. |
| `test_agents.py` | script | None | move to `scripts/` | Low | Agent manual test script. |
| `test_agents_basic.py` | script | None | move to `scripts/` | Low | Agent test utility. |
| `test_mcp.bat` | script | None | move to `scripts/` | Low | MCP batch test. |
| `test_mcp_config.js` | script | None | move to `scripts/` | Low | MCP config test. |
| `test_mcp_config.py` | script | None | move to `scripts/` | Low | MCP config test. |
| `ui_api_test.js` | script | None | move to `scripts/` | Low | UI API test script. |
| `validation_campaign.py` | script | None | move to `scripts/` | Low | Validation test script. |
| `verify_agents.py` | script | None | move to `scripts/` | Low | Verification script. |
| `TASK_COMPLETE.txt` | log/temp | None | delete | Low | Empty 0-byte temporary file. |
| `mastra.db*`, `test_e2e.db` | cache/db | Runtime SQLite | move to `artifacts/test_dbs/` | Low | Added to `.gitignore`. |
| `.coverage*` | cache | Pytest coverage | deleted from tracking | Low | Added to `.gitignore`. |
| `engineering_service.py` | source | Core API / CLI | keep | High | Core entrypoint. Kept at root. |
| `compat.py` | source | CI sync workflows | keep | High | Used in `.github/workflows/`. Kept at root. |
| `indexer.py` | source | CI auto-index | keep | High | Used in CI workflows. Kept at root. |
| `PROJECT_INDEX.*` | generated | CI indexing | keep | Medium | Used by CI workflows. Kept at root. |
| `validate_syntax.py` | script | CI quality gates | keep | High | Invoked by GitHub Actions. Kept at root. |
| `locustfile.py`, `k6-load-test.js` | test | CI load tests | keep | Medium | Invoked in CI. Kept at root. |
| `Dockerfile*` (5 files) | config | Docker builds | keep | High | Protected by rule. Kept at root. |
| `docker-compose*.yml` (6 files) | config | Compose orchestration | keep | High | Protected by rule. Kept at root. |
| `requirements*.txt` (8 files) | config | Dependencies | keep | High | Protected by rule. Kept at root. |
| `pyproject.toml`, `alembic.ini`, etc. | config | Build & Migration | keep | High | Protected by rule. Kept at root. |
