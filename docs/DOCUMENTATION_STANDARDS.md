---
title: "AhmedETAP Documentation Standards & Style Guide"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Core Team"
---

# 📜 AhmedETAP Documentation Standards & Style Guide

This document establishes the mandatory standards, stylistic conventions, and verification workflows for all technical documentation across the AhmedETAP project. It complies with **IEEE Std 26514-2018** (*Systems and software engineering — Requirements for designers and developers of user documentation*) and **ISO/IEC 26514:2008**.

---

## 📋 Table of Contents

- [1. Core Principles](#1-core-principles)
- [2. Metadata Frontmatter Specification](#2-metadata-frontmatter-specification)
- [3. Heading Hierarchy & Structure](#3-heading-hierarchy--structure)
- [4. Table of Contents Requirement](#4-table-of-contents-requirement)
- [5. Single Source of Truth (SSOT) Architecture](#5-single-source-of-truth-ssot-architecture)
- [6. Terminology & Glossary Cross-Referencing](#6-terminology--glossary-cross-referencing)
- [7. Procedural & Tutorial Writing Standards](#7-procedural--tutorial-writing-standards)
- [8. Bilingual Localization (EN / AR)](#8-bilingual-localization-en--ar)
- [9. Media Assets & Accessibility Standards](#9-media-assets--accessibility-standards)
- [10. Automated Verification & CI Quality Gates](#10-automated-verification--ci-quality-gates)

---

## 1. Core Principles

1. **Precision & Engineering Rigor:** Every statement about a calculation, standard, or system behavior must be verifiable against the underlying mathematical engine or international standard. Never make unsupported or ambiguous claims.
2. **Single Source of Truth:** No redundant manual documentation copies. The canonical API reference is [`docs/API_REFERENCE.md`](API_REFERENCE.md). Concise reference sheets ([`docs/API_QUICKREF.md`](API_QUICKREF.md)) must be generated or synchronized via automated scripts (`scripts/gen_api_ref.py`).
3. **Fail-Closed Verification:** CI pipelines must enforce link validity, asset existence, and metadata compliance on every commit.

---

## 2. Metadata Frontmatter Specification

Every document in the repository (root-level `.md` files and all documents in `docs/`) must begin with a standardized YAML frontmatter block:

```yaml
---
title: "<Document Title>"
version: "2.1.0"
last_updated: "YYYY-MM-DD"
maintainer: "<Team or Person Responsible>"
---
```

### Frontmatter Fields:
- `title` *(string, required)*: The clear, concise human-readable title of the document.
- `version` *(string, required)*: Semantic version of the project (e.g., `"2.1.0"`) or `"N/A"` for immutable archives.
- `last_updated` *(string, required)*: ISO 8601 date format (`"YYYY-MM-DD"`) corresponding to the last substantive technical modification.
- `maintainer` *(string, required)*: Responsible engineer or team (e.g., `"Eng. Ahmed Elbaz / Platform Core Team"`).

---

## 3. Heading Hierarchy & Structure

Follow a strict, logical markdown heading hierarchy:
- Use exactly **one** top-level `# Title` per document (placed immediately following the frontmatter).
- Use `## Section` for major topics.
- Use `### Subsection` for detailed components.
- Use `#### Component` for granular items.
- Never skip heading levels (e.g., do not jump directly from `#` to `###`).

---

## 4. Table of Contents Requirement

Every document containing **more than 800 words** must include a Table of Contents (TOC) directly below the document introduction and header badges:

```markdown
## 📋 Table of Contents

- [Section 1](#section-1)
  - [Subsection 1.1](#subsection-11)
- [Section 2](#section-2)
```

Anchors must match standard GitHub-flavored Markdown lowercase dashed slugs.

---

## 5. Single Source of Truth (SSOT) Architecture

To prevent drift, duplication of engineering documentation is strictly prohibited:

| Scope | Authoritative Source | Derivative / Deprecated Targets | Maintenance Policy |
| :--- | :--- | :--- | :--- |
| **API Endpoints & Schemas** | [`docs/API_REFERENCE.md`](API_REFERENCE.md) | [`docs/API_QUICKREF.md`](API_QUICKREF.md) | Synchronized via `scripts/gen_api_ref.py`. `API_DOCUMENTATION.md` is deprecated with forwarding banner. |
| **Project Version** | `VERSION` / `pyproject.toml` | Root & docs metadata | Version `"2.1.0"` pinned uniformly. |
| **Standards & Terminology** | [`docs/GLOSSARY.md`](GLOSSARY.md) | All doc cross-links | Link terms on first occurrence. |
| **Technical Debt** | [`docs/STATUS.md`](STATUS.md) | [`ROADMAP.md`](../ROADMAP.md) | Reconcile debt resolution status and empirical evidence. |

---

## 6. Terminology & Glossary Cross-Referencing

- Maintain comprehensive definitions in [`docs/GLOSSARY.md`](GLOSSARY.md) divided into:
  - **Abbreviations & Standards** (IEC, IEEE, SCADA, ADMS, BESS, Mastra, Goal Planner, etc.).
  - **Platform-Specific Terms** (ETAP Expert Skill, StudyType, Agent Handle, Prompt Manifest, Maker-Checker, etc.).
- **Rule of First Occurrence:** On the first mention of any technical abbreviation or proprietary concept in a document, hyperlink it directly to its glossary definition:
  - Example: `[IEC 60909](docs/GLOSSARY.md#iec-60909)` or `[IEEE 1584](docs/GLOSSARY.md#ieee-1584)`.

---

## 7. Procedural & Tutorial Writing Standards

In accordance with IEEE Std 26514-2018, every engineering tutorial (in `docs/TUTORIALS/`) must follow this mandatory 4-part structure:

1. **Prerequisites & Required Inputs:** Precise system requirements, software versions, base MVA, single-line diagrams, and complete valid JSON input payloads.
2. **Step-by-Step Execution Sequence:** Exact, copy-pasteable CLI commands (`curl`, Python API, or Mastra orchestration calls) in proper logical execution sequence.
3. **Expected Outputs & Engineering Validation Criteria:** Realistic response JSON, mathematical verification thresholds (e.g., bus voltage limits $0.95 \le V \le 1.05\text{ p.u.}$, arcing energy cutoff thresholds, and coordination time intervals $\text{CTI} \ge 0.30\text{ s}$).
4. **Troubleshooting & Remediation:** A tabular guide listing symptom, root cause, and concrete engineering remediation steps.

---

## 8. Bilingual Localization (EN / AR)

AhmedETAP supports native bilingual engineering teams:
- Core user-facing documents must have an equivalent Arabic translation:
  - `README.md` $\leftrightarrow$ `README.ar.md`
  - `QUICKSTART.md` $\leftrightarrow$ `QUICKSTART.ar.md`
  - `CONTRIBUTING.md` $\leftrightarrow$ `CONTRIBUTING.ar.md`
  - `SUPPORT.md` $\leftrightarrow$ `SUPPORT.ar.md`
- Provide a visible bilingual language switcher at the top of the document:
  ```markdown
  [English](<name>.md) | [العربية](<name>.ar.md)
  ```
- Arabic documents must maintain formal technical Arabic terminology (الفصحى التقنية) while preserving standard engineering acronyms (IEEE, IEC, kV, MVA).

---

## 9. Media Assets & Accessibility Standards

- All diagrammatic and screenshot assets must be stored in relative directories (`assets/`, `images/`, `docs/screenshots/`, or `docs/images/`).
- Markdown image embeds must use descriptive alternative text:
  ```markdown
  ![Single-Line Diagram of 33kV Substation](assets/substation_33kv_sld.png)
  ```
- Never use broken, unreferenced, or temporary absolute local paths (`C:\Users\...`).
- Verify asset integrity with `scripts/verify_assets.py`.

---

## 10. Automated Verification & CI Quality Gates

The documentation suite is protected by four automated quality gates:

1. **Frontmatter & Metadata Audit:**
   ```bash
   python scripts/check_metadata.py
   ```
   Validates that all major `.md` files contain complete frontmatter with current dates and maintainers.

2. **Asset Path Verification:**
   ```bash
   python scripts/verify_assets.py
   ```
   Ensures that 100% of image references point to valid, reachable local asset files.

3. **API Reference Synchronization:**
   ```bash
   python scripts/gen_api_ref.py --check
   ```
   Verifies that `docs/API_QUICKREF.md` matches the canonical endpoints in `docs/API_REFERENCE.md`.

4. **Link Integrity:**
   ```bash
   python scripts/check_links.py
   ```
   Validates internal anchor links and relative file targets across all markdown documents.
