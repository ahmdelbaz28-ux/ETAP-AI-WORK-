# Vercel Deployment Fix

## Problem

Vercel was reporting 520+ failed preview deploys, all with the message:

> Deployed `<commit>` with MkDocs version: 1.6.1 — Status: Failed to deploy

## Root Cause

Vercel **auto-detected MkDocs** as the deployment framework because `mkdocs.yml`
was present at the repository root. This auto-detection was overriding the
explicit `"framework": "vite"` setting in `vercel.json`.

Vercel then ran its MkDocs preset build, which fails because:

1. The MkDocs preset runs in strict mode, which converts the 40 broken-link
   warnings (markdown files referenced from `index.md` that don't exist in
   `docs/`) into hard build errors.
2. The MkDocs preset also expects `mkdocs-material` to be installed, which
   was not pinned anywhere in the project.

This was happening **despite** the project being explicitly configured to
deploy the Vite/React UI:

- `vercel.json` declares `framework: vite`, `buildCommand: npm --prefix ui run build:vercel`, `outputDirectory: ui/dist`
- `.vercelignore` has a comment: *"Vercel only builds the UI (vite framework, output to ui/dist/)"*

## Fix Applied

Moved `mkdocs.yml` from the repository root to `docs/mkdocs.yml`, and set
`docs_dir: .` inside it so MkDocs still finds its source files relative to
the new config location.

This prevents Vercel from auto-detecting MkDocs (Vercel only looks for
`mkdocs.yml` / `mkdocs.yaml` at the root directory of the project).

Local docs workflows continue to work — just point mkdocs at the moved file:

```bash
# Serve docs locally
mkdocs serve -f docs/mkdocs.yml

# Build docs locally
mkdocs build -f docs/mkdocs.yml --site-dir site
```

## Verification Performed Locally

| Step | Command | Result |
|---|---|---|
| Vite UI install | `cd ui && npm install --no-audit --no-fund` | OK — 733 packages |
| Vite UI build | `cd ui && npm run build:vercel` | OK — built in ~7s, output in `ui/dist/` |
| MkDocs build (moved config) | `mkdocs build -f docs/mkdocs.yml --site-dir /tmp/mkdocs-out` | OK — built in ~1.5s (40 link warnings, non-fatal) |

## Required Follow-up in Vercel Dashboard

Even with `mkdocs.yml` moved out of root, Vercel may still have the project's
**Framework Preset** sticky-set to "MkDocs" from when it was first detected.
Please verify the following in the Vercel dashboard:

1. Open the project: `ETAP-AI-WORK-`
2. Go to **Settings → General**
3. Under **Build & Development Settings**, verify:
   - **Framework Preset**: `Vite` (or `Other`)
   - **Build Command**: `npm --prefix ui run build:vercel` (or "Override" → use the vercel.json value)
   - **Output Directory**: `ui/dist` (or "Override" → use the vercel.json value)
   - **Install Command**: `npm --prefix ui install --no-audit --no-fund`
   - **Root Directory**: `(repo root)` — leave empty, NOT `ui/`
4. Under **Settings → Functions**, confirm no serverless functions are
   expected (this is a static SPA build).
5. Click **Save**.
6. Go to **Deployments** → click the most recent failed deploy → **Redeploy**.

## Files Changed

```
renamed:    mkdocs.yml -> docs/mkdocs.yml
```

Plus inline edits inside `docs/mkdocs.yml`:

- Added `docs_dir: .` (so MkDocs still finds its source files relative to the new config location).
- Added a header comment explaining the move and showing the local commands.
