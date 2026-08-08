# Security Exceptions — Known Vulnerabilities in Transitive Dependencies

This document records known Dependabot alerts for **transitive dependencies**
where an override would risk breaking the parent package. These exceptions are
accepted after risk assessment and tracked for future resolution.

---

## Exception 1: image-size (DoS via infinite loops)

| Field | Value |
|-------|-------|
| **Advisories** | GHSA-w3rx-r6r6-pgpr (ICNS), GHSA-5p2g-fcmc-qvqq (JXL/HEIF) |
| **Severity** | High |
| **Affected version** | image-size@1.2.1 |
| **Dependency chain** | `@mastra/memory@1.26.0` → `image-size@^1.2.0` |
| **Risk** | DoS — attacker-controlled image files can trigger infinite loops |
| **Mitigation** | Input validation upstream; untrusted images are not processed by @mastra/memory |
| **Why no override?** | `@mastra/memory` declares `image-size@^1.2.0`. Forcing 2.x is a **major version bump** with API changes that can break memory at runtime. |
| **Resolution path** | Track @mastra/memory releases; when it bumps image-size to 2.x, the alert auto-resolves. |
| **Review date** | 2026-08-08 |

## Exception 2: nanoid (infinite loop with size=0)

| Field | Value |
|-------|-------|
| **Advisory** | GHSA-pxhq-xw8m-5983 |
| **Severity** | High |
| **Affected version** | nanoid@3.3.18 |
| **Dependency chain** | `vitest@3.2.6` → `vite@7.3.6` → `postcss@8.5.26` → `nanoid@^3.3` |
| **Risk** | Custom generator with `size=0` loops infinitely |
| **Mitigation** | Our code never calls `nanoid` with `size=0`; this is a dev-only dependency |
| **Why no override?** | `postcss` declares `nanoid@^3.3` (CJS). nanoid@5.x is **ESM-only** — forcing it would cause `ERR_REQUIRE_ESM` and break the entire build. |
| **Resolution path** | Track postcss/vite releases; when they adopt nanoid 5.x+, the alert auto-resolves. |
| **Review date** | 2026-08-08 |

---

## Protocol

- **Never** add an `overrides` entry that forces a **major version bump** on a transitive dependency without verifying API compatibility and the parent package's explicit consent.
- **Always** document accepted vulnerabilities here with rationale and review date.
- **Review** exceptions quarterly; remove when upstream resolves.
