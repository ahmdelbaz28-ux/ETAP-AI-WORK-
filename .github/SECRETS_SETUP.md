# 🔐 GitHub Secrets & Variables Setup Guide — CI/CD Automation

This guide covers ALL secrets and variables required for the CI/CD automation
hardening pipeline. There are **19+ tokens/variables** that must be configured
before the full pipeline can run.

---

## 📋 Quick Setup (One-Liners)

### Prerequisites
```bash
# Install GitHub CLI
# macOS: brew install gh
# Linux: https://github.com/cli/cli/blob/trunk/docs/install_linux.md
# Windows: winget install GitHub.cli

gh auth login
```

### Repository Variables (Non-Sensitive IDs)

These are **NOT secrets** — they are public Azure subscription/tenant IDs.
Set them as **repository variables** (not secrets).

```bash
gh variable set AZURE_SUBSCRIPTION_ID -b "YOUR_AZURE_SUBSCRIPTION_ID"
gh variable set AZURE_TENANT_ID       -b "YOUR_AZURE_TENANT_ID"
gh variable set AZURE_CLIENT_ID       -b "YOUR_AZURE_CLIENT_ID"
```

### Repository Secrets (Sensitive Tokens)

```bash
# ── Cross-Platform Sync Secrets ──
gh secret set VERCEL_TOKEN        -b "YOUR_VERCEL_TOKEN"
gh secret set VERCEL_ORG_ID       -b "YOUR_VERCEL_ORG_ID"
gh secret set VERCEL_PROJECT_ID   -b "prj_YOUR_PROJECT_ID"
gh secret set HF_TOKEN            -b "hf_YOUR_HF_TOKEN"
gh secret set LANGWATCH_API_KEY   -b "sk-lw-YOUR_LANGWATCH_KEY"
gh secret set SMITHERY_API_KEY    -b "YOUR_SMITHERY_KEY"
gh secret set GH_PAT              -b "github_pat_YOUR_PAT"

# ── AI Service Keys ──
gh secret set OPENAI_API_KEY      -b "sk-YOUR_OPENAI_KEY"
gh secret set ANTHROPIC_API_KEY   -b "sk-ant-YOUR_ANTHROPIC_KEY"
gh secret set GOOGLE_API_KEY      -b "YOUR_GOOGLE_AI_KEY"

# ── Database & Infrastructure ──
gh secret set DATABASE_URL        -b "postgresql+asyncpg://user:pass@host:5432/db"
gh secret set REDIS_PASSWORD      -b "YOUR_REDIS_PASSWORD"
gh secret set JWT_SECRET_KEY      -b "YOUR_JWT_SECRET_KEY_MIN_32_BYTES"
gh secret set ENCRYPTION_KEY      -b "YOUR_ENCRYPTION_KEY_MIN_32_BYTES"
gh secret set ENGINEERING_SERVICE_API_KEY -b "YOUR_API_KEY"

# ── CI/CD Tooling ──
gh secret set SONAR_TOKEN         -b "YOUR_SONAR_TOKEN"
gh secret set DAYTONA_TOKEN       -b "day_YOUR_DAYTONA_TOKEN"
gh secret set CODECOV_TOKEN       -b "YOUR_CODECOV_TOKEN"
gh secret set NPM_TOKEN           -b "YOUR_NPM_TOKEN"
```

---

## 📖 Detailed Token Guide

### 1. Azure Variables (Terraform OIDC Auth)

| Variable | Where to Get | Used By |
|----------|-------------|---------|
| `AZURE_SUBSCRIPTION_ID` | Azure Portal → Subscriptions → Your subscription | `terraform.yml` |
| `AZURE_TENANT_ID` | Azure Portal → Azure AD → Properties → Tenant ID | `terraform.yml` |
| `AZURE_CLIENT_ID` | Azure Portal → App registrations → Your app → Application ID | `terraform.yml` |

These enable OIDC federated identity for Terraform (no stored secrets in GitHub).

### 2. Vercel Tokens

| Secret | Where to Get | Used By |
|--------|-------------|---------|
| `VERCEL_TOKEN` | Vercel → Settings → Tokens → Create (scope: Full Account) | `sync-platforms.yml`, `ci-cd.yml` |
| `VERCEL_ORG_ID` | Vercel → Settings → General → Your ID | `ci-cd.yml` |
| `VERCEL_PROJECT_ID` | Vercel → Project → Settings → General → Project ID | `ci-cd.yml`, `sync-platforms.yml` |

### 3. HuggingFace Token

| Secret | Where to Get | Used By |
|--------|-------------|---------|
| `HF_TOKEN` | https://huggingface.co/settings/tokens (Write scope) | `sync-platforms.yml`, `ci-cd.yml` |

### 4. AI Service Keys

| Secret | Where to Get | Used By |
|--------|-------------|---------|
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys | Application runtime |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/ | Application runtime |
| `GOOGLE_API_KEY` | https://aistudio.google.com/apikey | Application runtime |

### 5. Database & Infrastructure

| Secret | Where to Get | Used By |
|--------|-------------|---------|
| `DATABASE_URL` | Your PostgreSQL connection string | `ci-cd.yml`, `integration-tests.yml` |
| `REDIS_PASSWORD` | Your Redis password | `docker-compose.yml`, `ci-cd.yml` |
| `JWT_SECRET_KEY` | Generate: `openssl rand -hex 32` | Application runtime |
| `ENCRYPTION_KEY` | Generate: `openssl rand -hex 32` | Application runtime |
| `ENGINEERING_SERVICE_API_KEY` | Generate: `openssl rand -hex 32` | `docker-compose.yml`, `ci-cd.yml` |

### 6. CI/CD Tooling

| Secret | Where to Get | Used By |
|--------|-------------|---------|
| `SONAR_TOKEN` | https://sonarcloud.io/account/security | `ci-cd.yml` |
| `CODECOV_TOKEN` | https://app.codecov.io/gh/YOUR_REPO | `ci-cd.yml` |
| `DAYTONA_TOKEN` | Daytona → Settings → API Tokens | `daytona-ai-review.yml` |
| `LANGWATCH_API_KEY` | https://app.langwatch.ai/ | `sync-platforms.yml` |
| `SMITHERY_API_KEY` | https://smithery.ai/console/api-keys | `sync-platforms.yml` |
| `GH_PAT` | GitHub → Settings → Developer settings → PAT (Fine-grained) | `sync-platforms.yml` |
| `NPM_TOKEN` | https://www.npmjs.com/settings/tokens | `release.yml` |

---

## 🔑 Kubernetes Pre-Deploy Secret

Before deploying the Helm chart, create the `etap-api-key` secret:

```bash
# Option A: kubectl create (recommended — value not in git)
kubectl create secret generic etap-api-key \
  --from-literal=api-key=<your-real-api-key> \
  --namespace=ahmedetap

# Option B: sealed-secrets (production)
kubectl create secret generic etap-api-key \
  --from-literal=api-key=<your-real-api-key> \
  --namespace=ahmedetap \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > k8s/sealed-etap-api-key-secret.yaml

# Option C: external-secrets-operator (syncs from Azure KeyVault)
# See: https://external-secrets.io/latest/
```

---

## ✅ Verification

After setting all secrets, verify:

```bash
# Check which secrets are set
gh secret list

# Check which variables are set
gh variable list

# Verify the pipeline runs
git push origin main
# Then check: https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/actions
```

---

## ⚠️ Security Notes

1. **NEVER** commit real token values to git — use `gh secret set` or the GitHub web UI
2. **Rotate** tokens regularly (at least every 90 days)
3. **Use fine-grained PATs** with minimal scopes instead of classic tokens
4. **Enable Dependabot** to detect secrets accidentally committed
5. **Use OIDC** for Azure/Terraform auth instead of stored credentials
