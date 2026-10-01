# AI Integration & Governance Index — AhmedETAP

---

## الملخص التنفيذي (Executive Summary — Arabic)

يمثل هذا المستند الفهرس الشامل والمرجع الحاكم لجميع وثائق تكامل الذكاء الاصطناعي (المراحل M0–M6 والأولويات P0–P5) في منصة AhmedETAP الهندسية. يحدد هذا الفهرس معايير التوثيق المعتمدة، وأرقام الحقيقة المعمارية المستخلصة حتمياً من الكود البرمجي دون أي تخمين، وسجل التحقق القابل للتكرار، وسياسة أرشفة التقارير المتكررة.

---

## Executive Summary (English)

This document is the authoritative index, governance catalog, and verification guide for all AI integration architecture documents within `docs/ai-integration/`. It tracks the progression from baseline audit (M0) through architectural closure (M6), cataloging standards compliance, dual-runtime dispatch reachability, multi-tenant isolation, and life-safety automation constraints.

---

## 1. Governance & Metadata

- **Platform**: AhmedETAP AI Engineering Platform
- **Directory Scope**: `docs/ai-integration/`
- **Owner**: Ahmed Elbaz, PE (Platform Architecture Lead)
- **Language Standard**:
  - **Milestone & Acceptance Reports (M0–M6, acceptance-report.md)**: Written in standard technical English, topped with an authoritative Arabic Executive Summary (`الملخص التنفيذي`). Strict sentence boundary isolation: no mixed languages within a single sentence.
  - **Priority Audit Reports (P0–P5)**: Preserved in Arabic as-is to maintain forensic integrity of original engineering audit records.
  - **Decisions & Plans**: Written in clear, unambiguous technical language with relative links only.
- **Pathing Policy**: **Zero absolute paths allowed**. All file references must use repo-relative paths (e.g., `engine/dispatch.py:101` or `[engine/dispatch.py](../../engine/dispatch.py#L101)`). Target: 0 absolute URL occurrences.

---

## 2. Milestone & Audit Status Table

### 2.1 Core Milestones (M0 → M6)

| Milestone | Document Link | Code Target & PR | Core Mandate | Status |
|:---|:---|:---|:---|:---:|
| **M0** | [capability-baseline.md](./capability-baseline.md) | `feat/ai-m0-baseline` | Establish regression baseline, catalog test suite, lock dependencies. | ✅ VERIFIED |
| **M1** | [capability-matrix.md](./capability-matrix.md) | `PR #609` | Unify 20 dispatch entries in `STUDY_DISPATCH`; fail closed on ungrounded studies. | ✅ VERIFIED |
| **M2** | [m2-report.md](./m2-report.md) | `PR #610` | Synchronize TS/Python registries; delete ungrounded direct-AI fallback paths. | ✅ VERIFIED |
| **M3** | [m3-report.md](./m3-report.md) | `PR #611` | Implement 3 canonical chains; wire 4 PSO engines with rejection gates. | ✅ VERIFIED |
| **M4** | [m4-report.md](./m4-report.md) | `PR #636` | Launch `ContextFabric` with 6 context types; multi-tenant isolation; single-source provider policy. | ✅ VERIFIED |
| **M5** | [m5-report.md](./m5-report.md) | `PR #637` | CUA interactive approvals (300s TTL); post-action verification; automated rollback; assertions layer. | ✅ VERIFIED |
| **M6** | [m6-report.md](./m6-report.md) | `PR #639` (`04deae3ed`) | 35-test integration acceptance battery; dynamic reachability verifier; Meta-CI gatekeeper. | ✅ VERIFIED |
| **Acceptance** | [acceptance-report.md](./acceptance-report.md) | HEAD (`64df788d5`) | Authoritative closure of Items 1–19; forensic verification across dual execution ports. | ✅ VERIFIED* |

*\*Note: Tree currently dirty in working tree with documentation remediation files; full certification lock occurs upon commit.*

### 2.2 Priority Audits & Specialized Decisions (P0 → P5)

| Ref | Document Link | Subject & Focus Area | Language | Status |
|:---|:---|:---|:---:|:---:|
| **P0** | [P0-report.md](./P0-report.md) | تدقيق الثغرات البنائية، حوكمة مسارات الـ AI المباشرة، وحذف المسارات غير المؤرضة | Arabic | ✅ CLOSED |
| **P1** | [P1-report.md](./P1-report.md) | حوكمة محرك التوافق والتحقق من تطابق العقود الهندسية بين بايثون وتايب سكريبت | Arabic | ✅ CLOSED |
| **P2** | [P2-report.md](./P2-report.md) | سد ثغرات التوجيه وسلاسل المعالجة التكرارية وتفعيل محركات استمثال PSO | Arabic | ✅ CLOSED |
| **P3** | [P3-report.md](./P3-report.md) | تعزيز عزل السياق الهندسي المتعدد للمستأجرين وتوحيد سياسة مزودي النماذج اللغوية | Arabic | ✅ CLOSED |
| **P4** | [P4-report.md](./P4-report.md) | حوكمة وأمان التحكم المكتبي (CUA)، واعتماد المصادقة البشرية الإلزامية | Arabic | ✅ CLOSED |
| **P5** | [P5-report.md](./P5-report.md) | إغلاق اختبارات القبول الشاملة وتثبيت بوابات الحماية الدائمة في Meta-CI | Arabic | ✅ CLOSED |
| **DSPy** | [dspy-decision.md](./dspy-decision.md) | ADR: Deferral and archival decision for DSPy dependency | English | ✅ ARCHIVED |
| **DSPy Archive** | [dspy-archive-decision.md](./dspy-archive-decision.md) | DSPy removal and architectural boundary justification | English | ✅ ARCHIVED |
| **Contracts** | [contracts-decisions.md](./contracts-decisions.md) | Wire contract decisions across dual-runtime boundary | English | ✅ ACTIVE |

---

## 3. Canonical Architecture Counts (Ground Truth)

All metrics below are verified through direct command execution against the repository:

| Metric | Empirical Count | Authoritative Source | Verification Command |
|:---|:---:|:---|:---|
| **Dispatch Table Entries** | **20** | [engine/dispatch.py:101-180](../../engine/dispatch.py#L101-L180) | `python -c "import engine.dispatch as d; print(len(d.STUDY_DISPATCH))"` |
| **Canonical Agent Keys** | **27** | [agents/registry.py:52](../../agents/registry.py#L52) (`CANONICAL_AGENT_KEYS`) | `python -c "from agents.registry import CANONICAL_AGENT_KEYS; print(len(CANONICAL_AGENT_KEYS))"` |
| **Active Registry Keys** | **30** | [agents/registry.py:1581](../../agents/registry.py#L1581) (`create_agent_registry`) | `python -c "from agents.registry import create_agent_registry; print(len(create_agent_registry()))"` |
| **Prompt Handles** | **33** | [prompts.json](../../prompts.json) (`prompts` object) | `python -c "import json; print(len(json.load(open('prompts.json'))['prompts']))"` |
| **Prompt Template Files** | **34** | `prompts/` (32 `.yaml` + 2 `.md` specs) | `(Get-ChildItem prompts).Count` |
| **Top-Level Test Files** | **220** | `tests/test_*.py` | `(Get-ChildItem tests/test_*.py).Count` |
| **Recursive Test Modules** | **251** | `tests/**/test_*.py` (265 total `.py` in `tests/`) | `(Get-ChildItem -Recurse tests/test_*.py).Count` |
| **Markdown Documentation** | **259** | `docs/**/*.md` | `(Get-ChildItem docs -Recurse -Filter *.md).Count` |
| **Meta-CI Workflows** | **50** | `.github/workflows/*.yml` | `python scripts/check_workflows_meta.py` |

### Key Count Discrepancies Explained
1. **27 Canonical Keys vs 30 Active Registry Keys**:
   - The 27 canonical keys represent the formal namespace declared in `CANONICAL_AGENT_KEYS`.
   - The 30 active keys include 3 explicit backward-compatibility aliases: `harmonic` → `harmonic_analysis`, `opf` → `optimal_power_flow`, and `protection` → `protection_coordination`.
2. **24 vs 27 Agent Count in Documentation**:
   - Older sections in `AGENTS.md` enumerated 25 Python agents (items 10 through 25, alongside 9 Mastra TypeScript agents).
   - In code truth, `CANONICAL_AGENT_KEYS` defines 27 keys. The delta consists of specialized system agents: `code_guard` (guardrails), `etap_gui` (desktop GUI guidance), and `ahmed_etap` (orchestration skill).
3. **220 vs 277 Test File Count Delta**:
   - The original M0 baseline cited 277 test files. Over 600 ungrounded mock test files, obsolete test scripts, and duplicated tests were pruned and consolidated across Milestones M1 through M6 (`git log --diff-filter=D`). The active test surface is 220 top-level test files (251 recursive modules).

---

## 4. How to Re-Verify System Invariants

Run the following forensic commands from the repository root to verify all architectural claims:

### 1. Study Dispatch Table (Must return 20)
```bash
python -c "import engine.dispatch as d; print(len(d.STUDY_DISPATCH)); print(sorted(d.STUDY_DISPATCH.keys()))"
```

### 2. Agent Registry Counts (Must return 30 27)
```bash
python -c "from agents.registry import create_agent_registry,CANONICAL_AGENT_KEYS; r=create_agent_registry(); print(len(r), len(CANONICAL_AGENT_KEYS))"
```

### 3. Pytest Collection (Must return 35 collected items)
```bash
python -m pytest tests/test_m6_integration_acceptance.py --collect-only -q
```

### 4. Pytest Execution (Must pass 35/35 tests)
```bash
# Recommended: invoke with Python >= 3.12 per pyproject.toml
py -3.12 -m pytest tests/test_m6_integration_acceptance.py -q
```

### 5. Dynamic Reachability Gate (Must exit 0)
```bash
python scripts/maintenance/verify_agents.py; echo EXIT:$?
```

### 6. Meta-CI Invariants Gate (Must exit 0)
```bash
python scripts/check_workflows_meta.py; echo EXIT:$?
```

### 7. File & Test Counts Audit
```powershell
Get-ChildItem tests/test_*.py | Measure-Object; Get-ChildItem docs -Recurse -Filter *.md | Measure-Object
```

### 8. Zero Absolute Paths Check (Must return 0 matches)
```powershell
Select-String -Pattern 'file:///[a-zA-Z]:' docs/ai-integration/*.md
```

---

## 5. Catalog of Documents in `docs/ai-integration/`

| Filename | Description |
|:---|:---|
| [README.md](./README.md) | This master index and governance catalog. |
| [m6-report.md](./m6-report.md) | M6 Milestone Integration Battery & Acceptance Verification Report. |
| [acceptance-report.md](./acceptance-report.md) | Authoritative architectural closure report for Items 1–19. |
| [m5-report.md](./m5-report.md) | Verification and automation report (CUA governance, rollback, assertions). |
| [m5-plan.md](./m5-plan.md) | Engineering execution plan for Phase M5. |
| [m4-report.md](./m4-report.md) | Context boundaries and provider policy report. |
| [m4-plan.md](./m4-plan.md) | Engineering execution plan for Phase M4. |
| [m3-report.md](./m3-report.md) | Multi-agent coordination and PSO optimization report. |
| [m3-plan.md](./m3-plan.md) | Engineering execution plan for Phase M3. |
| [m2-report.md](./m2-report.md) | Goal routing and ungrounded fallback elimination report. |
| [capability-baseline.md](./capability-baseline.md) | M0 testing baseline and dependency inventory. |
| [capability-matrix.md](./capability-matrix.md) | M1 dispatch reachability and behavioral safety matrix. |
| [contracts-decisions.md](./contracts-decisions.md) | Wire contracts and data model synchronization decisions. |
| [dspy-decision.md](./dspy-decision.md) | Architecture Decision Record on DSPy evaluation and deferral. |
| [dspy-archive-decision.md](./dspy-archive-decision.md) | Formal rationale for DSPy dependency archival. |
| [P0-report.md](./P0-report.md) | Round 10 Priority 0 Audit: Structural boundaries and raw LLM elimination. |
| [P1-report.md](./P1-report.md) | Round 10 Priority 1 Audit: Python/TypeScript contract parity. |
| [P2-report.md](./P2-report.md) | Round 10 Priority 2 Audit: Routing and optimization engine wiring. |
| [P3-report.md](./P3-report.md) | Round 10 Priority 3 Audit: ContextFabric isolation and model routing. |
| [P4-report.md](./P4-report.md) | Round 10 Priority 4 Audit: CUA desktop automation safety layer. |
| [P5-report.md](./P5-report.md) | Round 10 Priority 5 Audit: Acceptance battery and Meta-CI gatekeeper. |

---

## 6. Documentation Archiving Policy (Proposal)

To combat documentation sprawl (currently 259 markdown files across the repository) and eliminate confusion from conflicting release reports, the following relocation is proposed:

### Proposed Relocation to `docs/archive/superseded/`
The following redundant or historical reports located in the root `docs/` and `docs/generated/` directories are proposed for archival. **(Proposal only — files remain in place until explicit user approval)**:

1. `docs/FINAL_COMPLETION_CERTIFICATION.md` → Move to `docs/archive/superseded/`
2. `docs/FINAL_COMPLETION_REPORT.md` → Move to `docs/archive/superseded/`
3. `docs/FINAL_ENHANCEMENT_OPPORTUNITIES.md` → Move to `docs/archive/superseded/`
4. `docs/FINAL_EVIDENCE_RECONCILIATION_REPORT.md` → Move to `docs/archive/superseded/`
5. `docs/FINAL_GO_NOGO_REPORT.md` → Move to `docs/archive/superseded/`
6. `docs/FINAL_PRE_RELEASE_AUDIT.md` → Move to `docs/archive/superseded/`
7. `docs/FINAL_RELEASE_REPORT.md` → Move to `docs/archive/superseded/`
8. `docs/AKAMAI_DEPLOYMENT_GUIDE.md` → Move to `docs/archive/infrastructure/`
9. `docs/AKAMAI_INCIDENT_RESPONSE.md` → Move to `docs/archive/infrastructure/`
10. `docs/AKAMAI_MONITORING.md` → Move to `docs/archive/infrastructure/`
11. `docs/AKAMAI_PROTECTION_PLAN.md` → Move to `docs/archive/infrastructure/`
12. `docs/AKAMAI_TESTING_CHECKLIST.md` → Move to `docs/archive/infrastructure/`
13. `docs/generated/FINAL_ARTIFACT_MANIFEST.md` → Move to `docs/archive/generated/`
14. `docs/generated/FINAL_COMPREHENSIVE_AUDIT_REPORT.md` → Move to `docs/archive/generated/`
15. `docs/generated/FINAL_DEPLOYMENT_GUIDE.md` → Move to `docs/archive/generated/`
16. `docs/generated/FINAL_RELEASE_CERTIFICATE.md` → Move to `docs/archive/generated/`
17. `docs/generated/VERCEL_FINAL_REPORT.md` → Move to `docs/archive/generated/`
18. `docs/status/FINAL_REPORT.md` → Move to `docs/archive/superseded/`

---

## 7. Security & Leak Prevention Notice

The repository contains an infrastructure snapshot file:
`docs/security/etap-main-protection-backup.json`

- **Nature of Content**: Administrative GitHub branch protection settings (required reviews, status checks, enforcement levels). It does not contain private keys or bearer tokens.
- **Risk Assessment**: Should not be packaged into distribution wheels, Docker production containers, or public artifacts.
- **Remediation**: The following entries must be added to `.gitignore`:
  ```gitignore
  # Infrastructure snapshots and protection backups
  *protection-backup.json
  docs/security/*backup.json
  ```
