# Security Policy

## Security Fixes Applied

This document outlines critical security vulnerabilities that have been addressed in this codebase.

### 1. Hardcoded API Keys Removed (model-config.ts)

**Location:** `src/mastra/lib/model-config.ts`

**Issue:** Hardcoded API key fallback values were present in the provider configuration, which would expose production API keys if environment variables were not set.

**Fix:** All hardcoded API key fallbacks have been replaced with empty string defaults (`''`). Providers without configured API keys will now be inactive.

**Before:**
```typescript
apiKey: process.env.QWEN_API_KEY || 'sk-ws-H.IIMXLP.5AXL.MEQCIGkHnN4eeXta1wKlderuajqskRV6x9_X9yemMBeLNhdOAiAgnfKI8iBnNgpxfM996fSgigOZ88eDFZO-gejbCwlrTA'
```

**After:**
```typescript
apiKey: process.env.QWEN_API_KEY || ''
```

**Related:** The `getActiveProvider()` function already checks for non-empty API keys (`p.apiKey`), ensuring inactive providers are skipped.

### 2. Kubernetes Secret Placeholders Updated (k8s-deployment.yaml)

**Location:** `k8s-deployment.yaml`

**Issue:** Base64-encoded secret values decoded to predictable strings ("change-me-in-production", "sk-placeholder").

**Fix:** Replaced with placeholder values that include clear instructions for proper secret generation:
- `jwt-secret-key`: Placeholder with generation instructions
- `openai-api-key`: Placeholder with generation instructions

**Instructions for Production:**

```bash
# Generate a strong JWT secret (recommended method)
JWT_SECRET=$(openssl rand -hex 32)
echo -n "$JWT_SECRET" | base64

# Or for your OpenAI API key
echo -n "your-openai-api-key-here" | base64
```

Apply the secret with:
```bash
kubectl apply -f k8s-deployment.yaml
```

Or update the secret separately:
```bash
kubectl create secret generic etap-secrets \
  --namespace=etap-platform \
  --from-literal=jwt-secret-key=<base64-encoded-secret> \
  --from-literal=openai-api-key=<base64-encoded-api-key> \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 3. Prompt Template Variable Corrected (etap_engineer_agent.yaml)

**Location:** `prompts/etap_engineer_agent.yaml`

**Issue:** User message template used `{{ environment_details }}` instead of the standard `{{input}}`.

**Fix:** Changed to `{{input}}` to match the convention used by other prompts in the codebase.

---

## Security Best Practices

### Environment Variables

1. **Never commit `.env` files** - They are excluded via `.gitignore`
2. **Never hardcode secrets** in source code, even as fallbacks
3. Use environment-specific configuration:
   - `.env.development` - Local development (non-sensitive defaults)
   - `.env.production` - Production secrets (never committed)

### API Key Management

1. **Rotate keys regularly** - Implement a key rotation schedule
2. **Use least-privilege keys** - Restrict API key permissions where possible
3. **Monitor key usage** - Enable logging and alerts for unusual API activity
4. **Use secret management** - In production, prefer:
   - Kubernetes Secrets with proper RBAC
   - HashiCorp Vault
   - AWS Secrets Manager / GCP Secret Manager
   - Azure Key Vault

### Kubernetes Deployment

1. **Always use HTTPS/TLS** - Enabled via cert-manager in the manifest
2. **Follow principle of least privilege** - Restrict service account permissions
3. **Enable audit logging** - Already configured via ConfigMap
4. **Use network policies** - Already configured to restrict pod communication
5. **Secrets are not encrypted at rest by default** - Enable EncryptionConfiguration in your cluster

### Development Workflow

1. **Run security audits** - Use tools like `npm audit` regularly
2. **Review dependencies** - Check for vulnerabilities in CI/CD pipeline
3. **Use pre-commit hooks** - Scan for secrets before commits

### Reporting Vulnerabilities

If you discover a security vulnerability, please report it by opening an issue or contacting the maintainers directly. Do not create public issues for sensitive security details.

---

## Environment Variables Reference

| Variable | Description | Required |
|----------|-------------|----------|
| `QWEN_API_KEY` | Primary Qwen/ Aliyun MaaS API key | No (fallback chain) |
| `QWEN2_API_KEY` | Secondary Qwen API key | No (fallback chain) |
| `GLM_API_KEY` | Modal/GLM API key | No (fallback chain) |
| `OPENAI_API_KEY` | OpenAI API key | No (fallback chain) |
| `JWT_SECRET_KEY` | Secret for JWT token signing | Yes (production) |
| `DATABASE_URL` | Database connection string | Optional |

At least one API key must be configured for the model configuration to work.